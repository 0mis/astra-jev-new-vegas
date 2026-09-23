"""Remember dispatched dialogue choices that return to the same ready menu.

NPC speech changing is not campaign progress. This supplies Jev with remaining
choices; it never chooses an answer or sends input itself.
"""
import hashlib,json,time
from planner_mailbox import atomic_json


class DialogueMemory:
    def __init__(self,path,pid):
        self.path=path;self.pid=pid;self.rows={}
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('pid')==pid and data.get('version')==1:
                self.rows=data.get('rows',{})
        except (OSError,ValueError):pass

    def filter(self,state,world,items,options,now=None):
        now=time.time() if now is None else now
        menus=[m for m in state.get('menus',[]) if m['name']=='dialogue']
        if not menus:return None,options,[]
        speaker=(world.get('crosshair') or {}).get('ref_id')
        if not speaker:
            speaker=next((x['text'] for x in menus[0]['labels'] if not x.get('target')),'unknown')
        context=[speaker,world.get('worldspace_id') or world.get('cell_id'),world.get('quest'),
                 sorted(o['text'] for o in world.get('objectives',[])),
                 sorted((o.get('quest',''),o.get('text','')) for o in world.get('journal',[])),
                 sorted(x['text'] for x in items)]
        key=hashlib.sha256(json.dumps(context).encode()).hexdigest()[:24]
        row=self.rows.get(key,{})
        counts=row.get('counts',{}) if 0<=now-row.get('at',0)<1800 else {}
        blocked=[label for label in options.values() if counts.get(label,0)>=2
                 and label.strip().rstrip('.!?').lower() not in ('goodbye','exit','back','leave')]
        return key,{ident:label for ident,label in options.items() if label not in blocked},blocked

    def record(self,key,text,now=None):
        if key is None:return
        now=time.time() if now is None else now
        row=self.rows.setdefault(key,{'at':now,'counts':{}})
        if not 0<=now-row['at']<1800:row['counts']={}
        row['at']=now;row['counts'][text]=row['counts'].get(text,0)+1
        self.rows=dict(sorted(self.rows.items(),key=lambda x:x[1]['at'])[-256:])
        atomic_json(self.path,{'version':1,'pid':self.pid,'rows':self.rows},best_effort=True)
