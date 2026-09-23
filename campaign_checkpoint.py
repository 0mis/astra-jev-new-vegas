"""Protect ordinary F5 saves after useful recorded campaign progress."""
import hashlib,json,math,pathlib,time
from game_input import act
from planner_mailbox import atomic_json
from jev_bridge import commentary
ROOT=pathlib.Path(__file__).resolve().parent

def should_checkpoint(state,world,last,now):
    player=state.get('player') or {}
    if (state.get('interface_mode')!=1 or state.get('vats_mode',0)!=0
        or player.get('life_state')!=0 or player.get('in_combat') or player.get('health_bar_fraction_approx',0)<.3):return False
    if any(m['name'] not in ('hud','tutorial') for m in state.get('menus',[])):return False
    labels={x['text'] for m in state.get('menus',[]) for x in m['labels']}
    if not {'HP','AP'}<=labels:return False
    if last and now-last['at']<15:return False
    if not last:return True
    return (player.get('cell_id')!=last.get('cell_id')
        or [x['text'] for x in world['objectives']]!=last.get('objectives')
        or player.get('equipped_weapon')!=last.get('weapon')
        or math.dist(player['position'],last['position'])>=1000)

def maybe_checkpoint(pid,recording,state,world,*,force=False):
    latest=ROOT/'save-checkpoint-latest.json'
    try:last=json.loads(latest.read_text(encoding='utf-8'))
    except (OSError,ValueError):last=None
    # Explicit preparation before a hazard can merit a save at the same place.
    # The HUD, life, combat, health and recording guards still apply.
    if not should_checkpoint(state,world,None if force else last,time.time()):return None
    config=pathlib.Path.home()/'OneDrive'/'Documents'/'My Games'/'FalloutNV'
    for name in ('Fallout.ini','FalloutPrefs.ini'):
        text=(config/name).read_text(encoding='utf-8-sig',errors='replace')
        if 'slocalsavepath=jevsaves\\' not in text.replace(' ','').lower():
            raise RuntimeError('Separate campaign save path is not verified; no F5 sent')
    source=config/'JevSaves'/'quicksave.fos'
    before=source.stat().st_mtime_ns if source.exists() else None
    act(pid,recording,keys=['f5'],seconds=.15,actor='Astra')
    until=time.monotonic()+5;stable=None;since=None
    while time.monotonic()<until:
        if source.exists():
            stat=source.stat();signature=(stat.st_size,stat.st_mtime_ns)
            if stat.st_mtime_ns!=before and stat.st_size>1000:
                if signature!=stable:stable=signature;since=time.monotonic()
                elif time.monotonic()-since>=.4:break
        time.sleep(.1)
    else:raise RuntimeError('F5 sent but new quicksave not verified; do not replay blindly')
    data=source.read_bytes();digest=hashlib.sha256(data).hexdigest()
    folder=ROOT/'checkpoints';folder.mkdir(exist_ok=True)
    name='autocheckpoint-'+time.strftime('%Y%m%dT%H%M%S')+'-'+digest[:8]+'.fos'
    target=folder/name
    with target.open('xb') as output:output.write(data)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise RuntimeError('Checkpoint copy hash mismatch')
    player=state['player'];row={'at':time.time(),'file':str(target.relative_to(ROOT)),'sha256':digest,'bytes':len(data),
        'cell_id':player['cell_id'],'cell_name':player.get('cell_name'),'position':player['position'],
        'weapon':player.get('equipped_weapon'),'health_fraction':player.get('health_bar_fraction_approx'),
        'objectives':[x['text'] for x in world['objectives']],'source':'ordinary recorded F5 input'}
    atomic_json(latest,row)
    commentary('Astra','Protected a new ordinary campaign quicksave in '+str(player.get('cell_name'))+'.','planner_summary')
    return {'checkpoint_created':row,'input_sent':True,'input_count':1}
