"""One fresh observed game decision, logged before the supervised executor acts."""
import argparse,json,pathlib,time,uuid
from observe_game import Observer
from jev_bridge import decide,commentary
from capture_progress import samples,numbers,advancing
ROOT=pathlib.Path(__file__).resolve().parent

def capture_quality(state,video_us,audio_us,now=None):
    """Preserve isolated driver warnings; stop on ongoing glitches or drift."""
    now=time.time() if now is None else now
    recent=[x for x in state.get('audio_warnings',[]) if now-x.get('at',0)<=30 and 'discontinuity' in x.get('message','').lower()]
    if len(recent)>=3:raise RuntimeError('Repeated audio glitches require capture repair')
    offset=state.get('audio_started_at',0)-state.get('video_launch_at',0)
    drift=(video_us-audio_us)/1_000_000-offset
    if abs(drift)>2:raise RuntimeError(f'Video/audio timeline drift exceeds two seconds: {drift:.3f}s')
    return {'audio_warning_count':state.get('audio_discontinuities',0),'timeline_difference_seconds':round(drift,3)}

def read_recording_state(folder):
    # Windows can briefly deny access while another process replaces the file.
    # Retry only this read, never any gameplay input or model request.
    for attempt in range(5):
        try:return json.loads((pathlib.Path(folder)/'session.json').read_text())
        except PermissionError:
            if attempt==4:raise
            time.sleep(.025)

def recording_health(folder):
    folder=pathlib.Path(folder)
    state=read_recording_state(folder)
    with (folder/'progress.txt').open('rb') as f:
        f.seek(0,2);size=f.tell();f.seek(max(0,size-4096))
        progress=f.read().decode('ascii',errors='ignore')
    video_records=samples(progress)
    frames=numbers(video_records,'frame')
    if (state['state']!='recording' or time.time()-state['last_update']>4 or
        state['audio_frames']<=0 or not advancing(frames) or
        time.time()-(folder/'progress.txt').stat().st_mtime>4):
        raise RuntimeError('Recording has not demonstrated fresh video and audio progress')
    quality={}
    if state.get('audio_codec')=='aac':
        audio_progress=folder/'audio-progress.txt'
        with audio_progress.open('rb') as f:
            f.seek(0,2);size=f.tell();f.seek(max(0,size-4096))
            audio_text=f.read().decode('ascii',errors='ignore')
        timestamps=numbers(samples(audio_text),'out_time_us')
        if not advancing(timestamps) or time.time()-audio_progress.stat().st_mtime>4:
            raise RuntimeError('AAC encoder has not demonstrated fresh audio progress')
        video_times=numbers(video_records,'out_time_us')
        if not video_times:raise RuntimeError('Video encoder timeline unavailable')
        quality=capture_quality(state,video_times[-1],timestamps[-1])
    return {'healthy':True,'video_frames':frames[-1],'audio_frames':state['audio_frames'],
            'session':folder.name,'checked_at':time.time(),'game_pid':state.get('game_pid'),
            'window_handle':state.get('window_handle'),'source_size':state.get('source_size'),**quality}

def main():
    p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True)
    p.add_argument('--request',required=True);p.add_argument('--recording',required=True)
    args=p.parse_args();request=json.loads(pathlib.Path(args.request).read_text(encoding='utf-8'))
    health=recording_health(args.recording);obs=Observer(args.pid)
    try:state=obs.snapshot()
    finally:obs.close()
    # The model receives only game state and the planner's public objective.
    # No credential, personal filesystem path, desktop image or private chat is sent.
    state.update(recording=health,objective=request['objective'],context=request.get('context',''))
    started=time.time();result=decide(state,request['options'],request['instructions'])
    result.update(request_id=str(uuid.uuid4()),requested_at=started,received_at=time.time(),
                  observed_at=state['observed_at'],objective=request['objective'],
                  observation=state,options=request['options'],executed=False)
    (ROOT/'latest-decision.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (ROOT/'decisions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result)+'\n')
    print(json.dumps({k:result[k] for k in ['request_id','choice','confidence','latency_seconds','observed_at','received_at']}))
    return 0
if __name__=='__main__':raise SystemExit(main())
