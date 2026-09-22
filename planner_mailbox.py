"""Nonblocking advisory exchange with this Codex task; no extra model client.

Advice is scoped to the observed quest stage and expires. The Jev loop keeps
choosing actions while Astra reads the latest request and writes new advice.
This module accepts data only, never executable code or requested shell actions.
"""
import hashlib,json,os,pathlib,time

ROOT=pathlib.Path(__file__).resolve().parent

def stage_key(state,world):
    payload=[state['player']['cell_id'],world.get('quest'),[o['text'] for o in world.get('objectives',[])]]
    return hashlib.sha256(json.dumps(payload,ensure_ascii=True).encode()).hexdigest()[:20]

def atomic_json(path,value,best_effort=False):
    path=pathlib.Path(path)
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.next')
    payload=json.dumps(value,indent=2)
    for attempt in range(8):
        try:
            temporary.write_text(payload,encoding='utf-8')
            temporary.replace(path)
            return True
        except PermissionError:
            if attempt==7:
                if best_effort:return False
                raise
            time.sleep(.025*(attempt+1))

def validated_advice(value,stage,now=None):
    now=time.time() if now is None else now
    if not isinstance(value,dict) or value.get('version')!=1 or value.get('stage')!=stage:return None
    if not isinstance(value.get('expires_at'),(float,int)) or value['expires_at']<=now:return None
    objective=value.get('objective');notes=value.get('notes',[])
    if not isinstance(objective,str) or not 1<=len(objective)<=600:return None
    if not isinstance(notes,list) or len(notes)>8 or any(not isinstance(x,str) or len(x)>500 for x in notes):return None
    return {'objective':objective,'notes':notes,'revision':value.get('revision')}

class PlannerMailbox:
    def __init__(self,root=ROOT):
        self.root=pathlib.Path(root);self.last_stage=None;self.last_publish=0

    def exchange(self,state,world,observation):
        now=time.time();stage=stage_key(state,world)
        if stage!=self.last_stage or now-self.last_publish>=5:
            if atomic_json(self.root/'planner-observation.json',{'version':1,'stage':stage,'observed_at':now,'observation':observation},best_effort=True):
                self.last_stage=stage;self.last_publish=now
        try:
            advice=validated_advice(json.loads((self.root/'planner-advice.json').read_text(encoding='utf-8')),stage,now)
        except (OSError,ValueError):advice=None
        return advice

    def request_help(self,state,world,reason):
        atomic_json(self.root/'planner-request.json',{'version':1,'stage':stage_key(state,world),'requested_at':time.time(),'reason':reason})
