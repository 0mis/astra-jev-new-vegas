"""Game-window video plus system loopback audio; never records the microphone."""
import argparse,datetime,json,pathlib,subprocess,time,wave,os,shutil,warnings,ctypes as c,ctypes.wintypes as w,queue,threading
import numpy as np
import soundcard as sc
import imageio_ffmpeg

def game_window(pid, title):
    from observe_game import Observer
    observer=Observer(pid);observer.close()
    user=c.WinDLL('user32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
    user.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
    user.IsWindowVisible.argtypes=[w.HWND]
    user.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
    matches=[]
    @c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    def visit(hwnd, _):
        owner=w.DWORD();user.GetWindowThreadProcessId(hwnd,c.byref(owner))
        if owner.value==pid and user.IsWindowVisible(hwnd):
            text=c.create_unicode_buffer(512);user.GetWindowTextW(hwnd,text,len(text))
            if text.value==title:matches.append(int(hwnd))
        return True
    user.EnumWindows(visit,0)
    if len(matches)!=1:raise RuntimeError('Expected exactly one visible window owned by the verified game')
    rect=w.RECT()
    if not user.GetClientRect(matches[0],c.byref(rect)):raise c.WinError(c.get_last_error())
    return matches[0],[rect.right-rect.left,rect.bottom-rect.top]

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
    p.add_argument("--game-pid",type=int,required=True)
    p.add_argument("--max-video-kbps",type=int,default=1500)
    p.add_argument("--audio-format",choices=['wav','aac'],default='aac')
    p.add_argument('--audio-buffer-frames',type=int,default=96000)
    p.add_argument('--audio-backend',choices=['wasapi_callback','soundcard'],default='wasapi_callback')
    args=p.parse_args()
    if not 500<=args.max_video_kbps<=8000:raise ValueError('Video rate must be 500 to 8000 kbps')
    if not 2048<=args.audio_buffer_frames<=96000:raise ValueError('Audio buffer outside supported bounds')
    hwnd,source_size=game_window(args.game_pid,args.title)
    folder=pathlib.Path(args.session).resolve()
    folder.mkdir(parents=True,exist_ok=False)
    exe=imageio_ffmpeg.get_ffmpeg_exe()
    log=(folder/"ffmpeg.log").open("wb")
    started=time.time()
    state={"state":"starting","title":args.title,"started_at":started,
           "recorder_pid":os.getpid(),"audio_frames":0,"audio_packets":0,
           "audio_peak":0.0,"audio_rate":48000,"audio_channels":2,
           "video_files":"video-%04d.mkv","audio_files":"audio-%04d."+args.audio_format,
           "game_pid":args.game_pid,"window_handle":hwnd,"source_size":source_size,
           "audio_codec":args.audio_format,"max_video_kbps":args.max_video_kbps,
           "microphone_recorded":False,"audio_discontinuities":0,"audio_warnings":[]}
    state['audio_buffer_frames']=args.audio_buffer_frames
    state['audio_backend']=args.audio_backend
    write_state(folder,state)
    cmd=[exe,"-hide_banner","-y","-f","gdigrab","-framerate","30","-draw_mouse","0",
         "-i","hwnd="+hex(hwnd),"-an","-vf","scale=1280:-2",
         "-c:v","libx264","-preset","veryfast","-crf","23","-maxrate",str(args.max_video_kbps)+'k',"-bufsize",str(2*args.max_video_kbps)+'k',
         "-pix_fmt","yuv420p","-g","60","-f","segment","-segment_time","1800",
         "-segment_format","matroska","-reset_timestamps","1",
         "-progress",str(folder/"progress.txt"),str(folder/"video-%04d.mkv")]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                          stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    state.update(encoder_pid=proc.pid,video_launch_at=time.time())
    audio=None; audio_proc=None; audio_log=None; audio_writer=None; audio_queue=queue.Queue(maxsize=100); writer_errors=[]; n=0; failure=None
    monitor=None;monitor_stop=threading.Event();monitor_errors=[]
    audio_task=None;avrt=None
    try:
        if args.audio_format=='aac':
            audio_log=(folder/'audio-ffmpeg.log').open('wb')
            audio_proc=subprocess.Popen([exe,'-hide_banner','-y','-f','s16le','-ar','48000','-ac','2','-probesize','32','-analyzeduration','0',
                '-i','pipe:0','-c:a','aac','-b:a','128k','-f','segment','-segment_time','1800',
                '-segment_format','adts','-reset_timestamps','1','-progress',str(folder/'audio-progress.txt'),
                str(folder/'audio-%04d.aac')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                stderr=audio_log,creationflags=subprocess.CREATE_NO_WINDOW)
            state['audio_encoder_pid']=audio_proc.pid
            def write_audio():
                try:
                    while True:
                        packet=audio_queue.get()
                        if packet is None:break
                        audio_proc.stdin.write(packet);audio_proc.stdin.flush()
                except BaseException as exc:writer_errors.append(str(exc))
            audio_writer=threading.Thread(target=write_audio,daemon=True);audio_writer.start()
        if args.audio_backend=='wasapi_callback':
            from loopback_audio import CallbackLoopback
            capture=CallbackLoopback();state['audio_device']=capture.device_name
        else:
            speaker=sc.default_speaker()
            if speaker is None:raise RuntimeError("No default playback device")
            loop=sc.get_microphone(id=speaker.id,include_loopback=True)
            if not loop.isloopback:raise RuntimeError("Refusing a microphone device")
            state["audio_device"]=speaker.name
            capture=loop.recorder(samplerate=48000,channels=[0,1],blocksize=args.audio_buffer_frames)
        def monitor_capture():
            # Filesystem checks and JSON publication can briefly block on Windows.
            # Keep them away from the audio capture thread and its finite buffer.
            try:
                while not monitor_stop.wait(.5):
                    if game_window(args.game_pid,args.title)[0]!=hwnd:raise RuntimeError('The recorded game window changed')
                    if shutil.disk_usage(folder).free<5*1024**3:raise RuntimeError('Recording stopped at 5GiB free-space reserve')
                    write_state(folder,state.copy())
            except BaseException as exc:monitor_errors.append(str(exc))
        monitor=threading.Thread(target=monitor_capture,daemon=True);monitor.start()
        # Ask Windows to schedule this capture thread as an audio task. This
        # applies only to the recorder thread and is reverted on finalization.
        avrt=c.WinDLL('avrt',use_last_error=True)
        avrt.AvSetMmThreadCharacteristicsW.argtypes=[w.LPCWSTR,c.POINTER(w.DWORD)]
        avrt.AvSetMmThreadCharacteristicsW.restype=w.HANDLE
        avrt.AvRevertMmThreadCharacteristics.argtypes=[w.HANDLE]
        avrt.AvRevertMmThreadCharacteristics.restype=w.BOOL
        task_index=w.DWORD()
        audio_task=avrt.AvSetMmThreadCharacteristicsW('Audio',c.byref(task_index))
        state['audio_scheduling']={'mmcss_audio':bool(audio_task),'error':0 if audio_task else c.get_last_error()}
        state['audio_scheduling']['mmcss_applies_to_capture']=args.audio_backend=='soundcard'
        with capture as rec:
            state["audio_started_at"]=time.time()
            while time.time()-started < args.seconds and not (folder/"stop.request").exists():
                if proc.poll() is not None:raise RuntimeError("Video encoder exited before recording finished")
                if audio_proc and audio_proc.poll() is not None:raise RuntimeError('Audio encoder exited before recording finished')
                if writer_errors:raise RuntimeError('Audio pipe failed: '+writer_errors[0])
                if monitor_errors:raise RuntimeError('Capture monitor failed: '+monitor_errors[0])
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    samples=rec.record(numframes=4800)
                for warning in caught:
                    message=str(warning.message)
                    event={'at':time.time(),'message':message,'captured_frames_before_packet':state['audio_frames'],
                           'capture_elapsed_seconds':time.time()-state['audio_started_at']}
                    state['audio_warnings'].append(event)
                    if 'discontinuity' in message.lower():state['audio_discontinuities']+=1
                if args.audio_backend=='wasapi_callback':
                    for event in rec.take_events():
                        state['audio_warnings'].append(event)
                        if 'discontinuity' in event['message'].lower():state['audio_discontinuities']+=1
                if args.audio_format=='wav' and (audio is None or n>=48000*1800):
                    if audio:audio.close()
                    index=state["audio_frames"]//(48000*1800)
                    audio=wave.open(str(folder/f"audio-{index:04d}.wav"),"wb")
                    audio.setnchannels(2);audio.setsampwidth(2);audio.setframerate(48000);n=0
                pcm=(np.clip(samples,-1,1)*32767).astype("<i2").tobytes()
                if audio_proc:
                    audio_queue.put_nowait(pcm)
                else:audio.writeframes(pcm)
                n+=len(samples)
                state["audio_frames"]+=len(samples);state["audio_packets"]+=1
                state["audio_peak"]=max(state["audio_peak"],float(np.abs(samples).max()))
                state.update(state="recording",last_update=time.time())
            state["stop_reason"]="stop_requested" if (folder/"stop.request").exists() else "duration_limit"
    except BaseException as exc:
        failure=f"{type(exc).__name__}: {exc}"
        state.update(state="failed",error=failure)
    finally:
        if audio_task and avrt:avrt.AvRevertMmThreadCharacteristics(audio_task)
        monitor_stop.set()
        if monitor:
            monitor.join(timeout=10)
            if monitor.is_alive():failure=failure or 'Capture monitor did not stop'
        if audio:audio.close()
        state["audio_finalized"]=audio is not None
        if audio_proc:
            try:
                audio_queue.put(None,timeout=2);audio_writer.join(timeout=15)
                if audio_writer.is_alive() or writer_errors:raise RuntimeError('Audio writer failed to flush all captured packets')
                audio_proc.stdin.close();audio_proc.wait(timeout=15)
            except Exception as exc:
                audio_proc.kill();audio_proc.wait();state['audio_stop_error']=str(exc)
            state['audio_exit_code']=audio_proc.returncode
            state['audio_finalized']=audio_proc.returncode==0
            if audio_proc.returncode:failure=failure or 'Audio encoder failed'
        if audio_log:audio_log.close()
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
