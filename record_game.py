"""Game-window video plus system loopback audio; never records the microphone."""
import argparse,datetime,json,pathlib,subprocess,time,wave,os,shutil,warnings
import numpy as np
import soundcard as sc
import imageio_ffmpeg

def write_state(folder,state):
    tmp=folder/"session.next.json"
    for retry in range(4):
        try:
            tmp.write_text(json.dumps(state,indent=2),encoding="utf-8")
            tmp.replace(folder/"session.json")
            return
        except PermissionError:
            if retry==3:raise
            time.sleep(.05)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--title",required=True)
    p.add_argument("--seconds",type=float,default=3600)
    p.add_argument("--session",required=True)
    args=p.parse_args()
    folder=pathlib.Path(args.session).resolve()
    folder.mkdir(parents=True,exist_ok=False)
    exe=imageio_ffmpeg.get_ffmpeg_exe()
    log=(folder/"ffmpeg.log").open("wb")
    started=time.time()
    state={"state":"starting","title":args.title,"started_at":started,
           "recorder_pid":os.getpid(),"audio_frames":0,"audio_packets":0,
           "audio_peak":0.0,"audio_rate":48000,"audio_channels":2,
           "video_files":"video-%04d.mkv","audio_files":"audio-%04d.wav",
           "microphone_recorded":False,"audio_discontinuities":0,"audio_warnings":[]}
    write_state(folder,state)
    cmd=[exe,"-hide_banner","-y","-f","gdigrab","-framerate","30","-draw_mouse","0",
         "-i","title="+args.title,"-an","-vf","scale=1280:-2",
         "-c:v","libx264","-preset","veryfast","-crf","23","-maxrate","4M","-bufsize","8M",
         "-pix_fmt","yuv420p","-g","60","-f","segment","-segment_time","1800",
         "-segment_format","matroska","-reset_timestamps","1",
         "-progress",str(folder/"progress.txt"),str(folder/"video-%04d.mkv")]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                          stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    state.update(encoder_pid=proc.pid,video_launch_at=time.time())
    audio=None; n=0; failure=None
    try:
        speaker=sc.default_speaker()
        if speaker is None:raise RuntimeError("No default playback device")
        loop=sc.get_microphone(id=speaker.id,include_loopback=True)
        if not loop.isloopback:raise RuntimeError("Refusing a microphone device")
        state["audio_device"]=speaker.name
        with loop.recorder(samplerate=48000,channels=[0,1],blocksize=2048) as rec:
            state["audio_started_at"]=time.time()
            while time.time()-started < args.seconds and not (folder/"stop.request").exists():
                if proc.poll() is not None:raise RuntimeError("Video encoder exited before recording finished")
                if shutil.disk_usage(folder).free < 5*1024**3:raise RuntimeError("Recording stopped at 5GiB free-space reserve")
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    samples=rec.record(numframes=4800)
                for warning in caught:
                    message=str(warning.message)
                    event={'at':time.time(),'message':message}
                    state['audio_warnings'].append(event)
                    if 'discontinuity' in message.lower():state['audio_discontinuities']+=1
                if audio is None or n>=48000*1800:
                    if audio:audio.close()
                    index=state["audio_frames"]//(48000*1800)
                    audio=wave.open(str(folder/f"audio-{index:04d}.wav"),"wb")
                    audio.setnchannels(2);audio.setsampwidth(2);audio.setframerate(48000);n=0
                pcm=(np.clip(samples,-1,1)*32767).astype("<i2").tobytes()
                audio.writeframes(pcm)
                n+=len(samples)
                state["audio_frames"]+=len(samples);state["audio_packets"]+=1
                state["audio_peak"]=max(state["audio_peak"],float(np.abs(samples).max()))
                state.update(state="recording",last_update=time.time())
                if state["audio_packets"]%10==0:write_state(folder,state)
            state["stop_reason"]="stop_requested" if (folder/"stop.request").exists() else "duration_limit"
    except BaseException as exc:
        failure=f"{type(exc).__name__}: {exc}"
        state.update(state="failed",error=failure)
    finally:
        if audio:audio.close()
        state["audio_finalized"]=audio is not None
        try:
            if proc.poll() is None:
                proc.stdin.write(b"q\n");proc.stdin.flush()
            proc.wait(timeout=15)
        except Exception as exc:
            proc.kill();proc.wait()
            state["video_stop_error"]=str(exc)
        log.close()
        state.update(video_exit_code=proc.returncode,finalized_at=time.time(),
                     state="failed" if failure or proc.returncode else "stopped")
        write_state(folder,state)
    print(json.dumps({k:state.get(k) for k in ["state","error","audio_frames","audio_packets","audio_peak","audio_finalized","video_exit_code"]}))
    return 1 if state["state"]=="failed" else 0

if __name__=="__main__":raise SystemExit(main())
