"""Astra's observed map/landmark destination; Jev still chooses the inputs."""
import json,math,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parent

def objective_handoff(state,world,path=None,now=None):
    """A planned stage transition must not fall back to an unrelated nearby door."""
    try:
        plan=json.loads((path or ROOT/'planner-destination.json').read_text(encoding='utf-8'))
        player=state.get('player') or {};quest=world.get('quest');objectives=world.get('objectives')
        if (plan.get('version')!=1 or plan.get('handoff_on_objective_change') is not True
            or plan['expires_at']<=(time.time() if now is None else now)
            or state.get('interface_mode')!=1 or player.get('life_state')!=0
            or not isinstance(plan.get('quest'),str) or not plan['quest']
            or not isinstance(plan.get('objective_contains'),str) or not plan['objective_contains']
            or not isinstance(quest,str) or not quest
            or not isinstance(objectives,list) or not objectives
            or not all(isinstance(o,dict) and isinstance(o.get('text'),str) and o['text'] for o in objectives)):
            return None
        if quest!=plan['quest'] or not any(plan['objective_contains'] in o['text'] for o in objectives):
            return 'The planned quest objective changed; inspect the new objective before further travel.'
    except (OSError,ValueError,TypeError,KeyError):pass
    return None

def scope_handoff(state,world,path=None,now=None):
    """Stop once after a requested doorway transition, regardless of spawn offset."""
    try:
        plan=json.loads((path or ROOT/'planner-destination.json').read_text(encoding='utf-8'))
        scopes=plan.get('handoff_scopes',[]);player=state.get('player') or {}
        if (plan.get('version')!=1 or plan['expires_at']<=(time.time() if now is None else now)
            or plan.get('quest')!=world.get('quest') or player.get('life_state')!=0 or player.get('in_combat')
            or state.get('interface_mode')!=1 or not isinstance(scopes,list) or not 1<=len(scopes)<=8
            or not all(isinstance(x,str) for x in scopes)
            or not isinstance(plan.get('objective_contains'),str) or not plan['objective_contains']):return None
        if not any(plan['objective_contains'] in o['text'] for o in world.get('objectives',[])):return None
        scope=world.get('worldspace_id') or player.get('cell_id')
        if scope in scopes:return 'Reached the requested destination area '+scope+'; hand off before further travel.'
    except (OSError,ValueError,TypeError,KeyError):pass
    return None

def course_target(plan,scope,origin,progress):
    """Advance an ordered observed route only after reaching its next point."""
    course=plan.get('course');revision=plan.get('revision')
    if (plan.get('scope')!=scope or not origin or not isinstance(revision,str)
        or not revision or not isinstance(course,list) or not 1<=len(course)<=64):return None
    for row in course:
        if (not isinstance(row,dict) or row.get('kind')!=0
            or not isinstance(row.get('ref_id'),str) or not isinstance(row.get('name'),str)
            or not isinstance(row.get('position'),list) or len(row['position'])!=3
            or not all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<1e7 for v in row['position'])):return None
    radius=plan.get('course_radius',155)
    if not isinstance(radius,(int,float)) or not 50<=radius<=200:return None
    index=progress.get('index',0) if progress.get('revision')==revision else 0
    if not isinstance(index,int) or not 0<=index<len(course):return None
    while index<len(course)-1:
        point=course[index]['position']
        if math.dist(origin[:2],point[:2])>radius or abs(origin[2]-point[2])>240:break
        index+=1
    return dict(course[index],course_radius=radius),{'revision':revision,'index':index}


def scoped_target(plan,scope,origin):
    """Observed street partitions can share one exterior worldspace."""
    regions=plan.get('regions',[])
    if not isinstance(regions,list) or len(regions)>16:return None
    if origin:
        for region in regions:
            if not isinstance(region,dict):return None
            if region.get('scope')!=scope:continue
            bounds=region.get('bounds_xy')
            if (not isinstance(bounds,list) or len(bounds)!=4
                or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in bounds)
                or bounds[0]>=bounds[2] or bounds[1]>=bounds[3]):return None
            if bounds[0]<=origin[0]<bounds[2] and bounds[1]<=origin[1]<bounds[3]:
                return region.get('target')
    row=plan.get('targets_by_scope',{}).get(scope)
    if row is None and plan.get('scope')==scope:row=plan.get('target')
    return row

def destination(world,path=None,now=None):
    try:
        path=path or ROOT/'planner-destination.json'
        plan=json.loads(path.read_text(encoding='utf-8'))
        now=time.time() if now is None else now
        if plan.get('version')!=1 or plan['expires_at']<=now:return None
        scope=world.get('worldspace_id') or world.get('cell_id')
        if not any(plan['objective_contains'] in o['text'] for o in world['objectives']):return None
        if 'course' in plan:
            progress_path=path.with_name('planner-route-progress.json')
            try:progress=json.loads(progress_path.read_text(encoding='utf-8'))
            except (OSError,ValueError):progress={}
            if not isinstance(progress,dict):return None
            selected=course_target(plan,scope,world.get('camera_position'),progress)
            if not selected:return None
            row,updated=selected
            if updated!=progress:
                from planner_mailbox import atomic_json
                atomic_json(progress_path,updated)
        else:row=scoped_target(plan,scope,world.get('camera_position'))
        if row is None:return None
        pos=row['position'];origin=world['camera_position'];camera=world['camera_view']
        if (not isinstance(row['ref_id'],str) or not isinstance(row['name'],str)
            or row['kind'] not in (0,21,22,23,28,39,42,43) or len(pos)!=3
            or not all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<1e7 for v in pos)
            or not origin or not camera):return None
        # Refresh real loaded actors/doors rather than steering at stale positions.
        candidates=(world.get('doors',[])+world.get('furniture',[])+world.get('actors',[])+world.get('terminals',[])
                    +world.get('nearby',[])+([world['crosshair']] if world.get('crosshair') else []))
        live=next((r for r in candidates
                   if r['ref_id']==row['ref_id'] and r.get('same_space')),None)
        result=dict(live or row)
        delta=[a-b for a,b in zip(result['position'],origin)]
        result.update(distance=round(math.hypot(*delta[:2]),1),
            heading_error=round((math.atan2(delta[0],delta[1])-camera['yaw']+math.pi)%(2*math.pi)-math.pi,5),
            quest_target=True,objective_text=plan['purpose'],route_source=plan.get('source','Astra plan from observed map or loaded landmark'),
            same_space=True,loaded=bool(live and live.get('loaded')),remembered=not bool(live))
        result['name']=row['name']
        if 'course' in plan:result['planner_course_revision']=plan['revision']
        result.pop('planner_arrival_radius',None)
        radius=plan.get('arrival_radius',155)
        final_point='course' not in plan or updated['index']==len(plan['course'])-1
        if (plan.get('handoff_on_arrival') is True and final_point and result.get('kind')==0
            and isinstance(radius,(int,float)) and 50<=radius<=200):
            result['planner_arrival_radius']=radius
        return result
    except (OSError,ValueError,TypeError,KeyError):return None
