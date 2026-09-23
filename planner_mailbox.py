"""Nonblocking advisory exchange with this Codex task; no extra model client.

Advice is scoped to the observed quest stage and expires. The Jev loop keeps
choosing actions while Astra reads the latest request and writes new advice.
This module accepts data only, never executable code or requested shell actions.
"""
import hashlib,json,os,pathlib,time

ROOT=pathlib.Path(__file__).resolve().parent

def stage_key(state,world):
    payload=[world.get('worldspace_id') or state['player']['cell_id'],world.get('quest'),[o['text'] for o in world.get('objectives',[])]]
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
    result={'objective':objective,'notes':notes,'revision':value.get('revision')}
    if value.get('avoid_combat') is True:result['avoid_combat']=True
    exclusions=value.get('dialogue_exclusions',{})
    if (isinstance(exclusions,dict) and len(exclusions)<=8
        and all(isinstance(speaker,str) and 1<=len(speaker)<=120
                and isinstance(labels,list) and len(labels)<=12
                and all(isinstance(label,str) and 1<=len(label)<=600 for label in labels)
                for speaker,labels in exclusions.items())):
        result['dialogue_exclusions']=exclusions
    return result

def restrict_world_options(options,advice):
    """An explicit escape order retains movement/healing but excludes attacks."""
    if (advice or {}).get('avoid_combat') is not True:return options
    return {key:value for key,value in options.items()
            if key not in ('fire','vats') and not key.startswith('shoot:')}


def restrict_dialogue_options(state,advice,options):
    """Exclude exact observed labels only for the speaker in scoped advice."""
    exclusions=(advice or {}).get('dialogue_exclusions',{})
    speakers={label.get('text') for menu in state.get('menus',[]) if menu.get('name')=='dialogue'
              for label in menu.get('labels',[]) if label.get('path','').endswith('/DM_SpeakerNameLabel')}
    # An ambiguous or missing speaker cannot activate encounter restrictions.
    blocked=exclusions.get(next(iter(speakers)),[]) if len(speakers)==1 else []
    removed=[label for key,label in options.items() if key.isdigit() and label in blocked]
    return {key:label for key,label in options.items() if not key.isdigit() or label not in blocked},removed

def advice_for_world(value,stage,state,world,now=None):
    advice=validated_advice(value,stage,now)
    if not isinstance(value,dict):return None
    scope=world.get('worldspace_id') or state.get('player',{}).get('cell_id')
    def scoped(result):
        goals=value.get('objectives_by_scope',{})
        goal=goals.get(scope) if isinstance(goals,dict) and len(goals)<=8 else None
        if result and isinstance(goal,str) and 1<=len(goal)<=600:
            result=dict(result,objective=goal)
        transition=value.get('equipment_transition')
        if result and isinstance(transition,dict) and transition.get('scope')==scope:
            weapon=transition.get('weapon');next_goal=transition.get('then')
            if (isinstance(weapon,str) and 1<=len(weapon)<=120
                and isinstance(next_goal,str) and 1<=len(next_goal)<=600
                and state.get('player',{}).get('equipped_weapon')==weapon):
                result=dict(result,objective=next_goal)
        return result
    if advice:return scoped(advice)
    continuity=value.get('continuity',{})
    if not isinstance(continuity,dict):return None
    scopes=continuity.get('scopes',[])
    fragment=continuity.get('objective_contains')
    if (not isinstance(scopes,list) or not 1<=len(scopes)<=8 or scope not in scopes
        or continuity.get('quest')!=world.get('quest')
        or not isinstance(fragment,str) or not fragment
        or not any(fragment in o['text'] for o in world.get('objectives',[]))):return None
    # Carry the same intent through explicitly approved doorway scopes only.
    # Expiration and content validation still apply; coordinates stay separate.
    return scoped(validated_advice(value,value.get('stage'),now))

class PlannerMailbox:
    def __init__(self,root=ROOT):
        self.root=pathlib.Path(root);self.last_stage=None;self.last_publish=0

    def exchange(self,state,world,observation):
        now=time.time();stage=stage_key(state,world)
        if stage!=self.last_stage or now-self.last_publish>=5:
            if atomic_json(self.root/'planner-observation.json',{'version':1,'stage':stage,'observed_at':now,'observation':observation},best_effort=True):
                self.last_stage=stage;self.last_publish=now
        try:
            advice=advice_for_world(json.loads((self.root/'planner-advice.json').read_text(encoding='utf-8')),stage,state,world,now)
        except (OSError,ValueError):advice=None
        return advice

    def request_help(self,state,world,reason):
        atomic_json(self.root/'planner-request.json',{'version':1,'stage':stage_key(state,world),'requested_at':time.time(),'reason':reason})
