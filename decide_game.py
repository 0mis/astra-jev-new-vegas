"""One fresh observed game decision, logged before the supervised executor acts."""
import argparse,json,pathlib,time,uuid
from observe_game import Observer
from jev_bridge import decide,commentary
ROOT=pathlib.Path(__file__).resolve().parent

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
    frames=[int(line.split('=',1)[1]) for line in progress.splitlines() if line.startswith('frame=')]
    if (state['state']!='recording' or time.time()-state['last_update']>4 or
        state['audio_frames']<=0 or len(frames)<2 or frames[-1]<=frames[-2] or
        time.time()-(folder/'progress.txt').stat().st_mtime>4):
        raise RuntimeError('Recording has not demonstrated fresh video and audio progress')
    if state.get('audio_codec')=='aac':
        audio_progress=folder/'audio-progress.txt'
        with audio_progress.open('rb') as f:
            f.seek(0,2);size=f.tell();f.seek(max(0,size-4096))
            audio_text=f.read().decode('ascii',errors='ignore')
        timestamps=[int(line.split('=',1)[1]) for line in audio_text.splitlines() if line.startswith('out_time_us=') and line.split('=',1)[1].lstrip('-').isdigit()]
        if len(timestamps)<2 or timestamps[-1]<=timestamps[-2] or time.time()-audio_progress.stat().st_mtime>4:
            raise RuntimeError('AAC encoder has not demonstrated fresh audio progress')
    return {'healthy':True,'video_frames':frames[-1],'audio_frames':state['audio_frames'],
            'session':folder.name,'checked_at':time.time(),'game_pid':state.get('game_pid'),
            'window_handle':state.get('window_handle'),'source_size':state.get('source_size')}

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
