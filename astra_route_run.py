"""Short supervised traversal; normal guarded inputs, read-only observations."""
import argparse,json,math,time
from pathlib import Path
from observe_game import Observer
from world_controller import WorldController
from game_input import act,pause_world
from decide_game import recording_health

def main():
 p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--recording',required=True)
 p.add_argument('--ref',required=True);p.add_argument('--position',nargs=3,type=float,required=True)
 p.add_argument('--seconds',type=float,default=18);p.add_argument('--output',required=True);p.add_argument('--min-health',type=float,default=.12)
 p.add_argument('--arrival-distance',type=float,default=220)
 a=p.parse_args();assert 0<a.seconds<=45 and 0<=a.min_health<=1
 assert 50<=a.arrival_distance<=2000
 rec=Path(a.recording);obs=Observer(a.pid);c=WorldController();events=[];reason='time bound reached'
 print('capture',json.dumps(recording_health(rec)),flush=True)
 try:
  s=obs.snapshot()
  if s['interface_mode']==2 and any(m['name']=='start' and any(x['text']=='Continue' for x in m['labels']) for m in s['menus']):
   act(a.pid,rec,keys=['escape'],seconds=.08);time.sleep(.25)
  end=time.monotonic()+a.seconds;blocked=0
  while time.monotonic()<end:
   s=obs.snapshot(False);pl=s['player']
   if s['interface_mode']!=1 or pl['life_state']!=0 or pl.get('health_bar_fraction_approx',1)<a.min_health:
    reason='game or health transition';break
   w=obs.world(s)
   if w['disabled_controls']['movement'] or w['disabled_controls']['look']:
    reason='scripted control transition';break
   t={'ref_id':a.ref,'name':'Observed supervised destination','kind':28,'position':a.position}
   live=next((x for x in w['doors']+w['actors']+w['furniture'] if x['ref_id']==a.ref),None)
   if live:t=live
   t['distance']=math.dist(pl['position'][:2],t['position'][:2])
   if t['distance']<a.arrival_distance:reason='destination approach reached';break
   kw=c.target_input(obs,s,w,t,'route')
   if not any(kw.get(k) for k in ('keys','dx','dy')):reason='empty movement';break
   r=act(a.pid,rec,poll_menu_labels=False,stop_when=lambda x:x.get('interface_mode')!=1 or x.get('player',{}).get('life_state')!=0 or x.get('player',{}).get('health_bar_fraction_approx',1)<a.min_health,**kw)
   after=r['after']['player'];moved=math.dist(pl['position'][:2],after['position'][:2]);events.append({'at':time.time(),'position':after['position'],'health':after.get('health_bar_fraction_approx'),'moved':moved})
   blocked=blocked+1 if kw.get('keys') and moved<15 else 0
   if blocked>=2:reason='physical obstruction';break
 finally:
  pause=pause_world(a.pid);s=obs.snapshot();obs.close()
  result={'at':time.time(),'actor':'Astra','reason':reason,'events':events,'pause':pause,'final':s['player'],'menus':s['menus']}
  Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
  print(json.dumps({'reason':reason,'steps':len(events),'final':s['player'],'menus':[m['name'] for m in s['menus']],'pause':pause}),flush=True)
if __name__=='__main__':main()
