"""Choose one observed dialogue topic and wait for its response; normal input only."""
import argparse,json,time
from pathlib import Path
from observe_game import Observer
from game_input import point_cursor,act
from jev_bridge import commentary

def topics(state):
 return [x for m in state['menus'] if m['name']=='dialogue' for x in m['labels'] if x.get('target') and '/DM_TopicList/' in x['path']]

def main():
 p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--recording',required=True);p.add_argument('--speaker',required=True);p.add_argument('--contains',required=True);a=p.parse_args()
 obs=Observer(a.pid)
 try:
  s=obs.snapshot();labels=[x for m in s['menus'] if m['name']=='dialogue' for x in m['labels']]
  assert any(x['text']==a.speaker and 'SpeakerName' in x['path'] for x in labels),'Speaker changed'
  old=topics(s);matches=[x for x in old if a.contains in x['text']];assert len(matches)==1,'Topic is not unique and visible'
  topic=matches[0];point_cursor(a.pid,Path(a.recording),.75*(topic['x']+topic['width']*.45),.75*(topic['y']+topic['height']/2))
  fresh=topics(obs.snapshot());assert any(x['tile']==topic['tile'] and x['text']==topic['text'] and x.get('highlighted') for x in fresh),'Hover did not select intended topic'
  act(a.pid,Path(a.recording),button='left',seconds=.1)
  commentary('Astra','Selected dialogue: '+topic['text'],'selected_action')
  print(json.dumps({'selected':topic['text']}),flush=True)
  deadline=time.monotonic()+45;old_text=[x['text'] for x in old]
  while time.monotonic()<deadline:
   s=obs.snapshot();current=topics(s)
   if not any(m['name']=='dialogue' for m in s['menus']):break
   if current and [x['text'] for x in current]!=old_text:break
   time.sleep(.2)
  print(json.dumps({'mode':s['interface_mode'],'player':s['player'],'menus':[{'name':m['name'],'text':list(dict.fromkeys(x['text'] for x in m['labels']))} for m in s['menus']]}),flush=True)
 finally:obs.close()

if __name__=='__main__':main()
