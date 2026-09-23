"""Bounded execution of Jev's chosen Nellis course, with frequent live checks."""
import json,math,time
from pathlib import Path
from damage_watch import nellis_artillery_traversal
from planner_destination import destination
from game_input import act
import healing_hotkey

def allowed(state,world,target):
    player=state.get('player') or {}
    return bool(target and target.get('prefer_direct') and state.get('interface_mode')==1
        and not state.get('vats_mode') and player.get('life_state')==0 and not player.get('in_combat')
        and not any(m['name'] not in ('hud','tutorial') for m in state.get('menus',[]))
        and not world.get('disabled_controls',{}).get('movement',True)
        and not world.get('disabled_controls',{}).get('look',True)
        and nellis_artillery_traversal(world,player,{target['ref_id']:target}))

def execute(controller,observer,pid,recording,request_id):
    started=time.monotonic();until=started+12;inputs=0;heals=[];blocked=0;last_heal=-100
    initial=observer.snapshot();origin=initial['player']['position'];reason=None;visited=[];revision=None
    for step in range(48):
        if time.monotonic()>=until:break
        state=observer.snapshot();world=observer.world(state,nearby_ref_ids=())
        target=destination(world)
        if not allowed(state,world,target):
            reason='Course traversal stopped for changed game state, controls or plan.';break
        if revision is None:revision=target.get('planner_course_revision')
        if not revision or target.get('planner_course_revision')!=revision:
            reason='Course plan changed during traversal; return to Jev for a fresh decision.';break
        from world_controller import reached_planner_waypoint
        if reached_planner_waypoint(state['player'],{target['ref_id']:target}):
            reason='Reached the final planned Nellis approach waypoint; inspect the actual fence.';break
        visited.append(target['ref_id'])
        kwargs=controller.target_input(observer,state,world,target,'route')
        moving=bool(kwargs.get('keys'))
        if not any(kwargs.get(k) for k in ('keys','dx','dy')):
            reason='Course waypoint produced no movement; inspect before repeating.';break
        item=healing_hotkey.binding(observer)
        if (moving and state['player'].get('health_bar_fraction_approx',1)<.7
            and time.monotonic()-last_heal>=1 and healing_hotkey.available(state,item)):
            heal=healing_hotkey.use(observer,pid,recording,request_id+':heal:'+str(step),move_forward=True)
            inputs+=heal.get('input_count',0)
            if heal.get('handoff'):
                reason=heal['handoff'];break
            if heal.get('result'):heals.append(heal['result'])
            last_heal=time.monotonic()
            continue
        kwargs['seconds']=min(kwargs['seconds'],.8,max(.05,until-time.monotonic()))
        before=state['player']['position']
        result=act(pid,recording,actor='Jev',request_id=request_id+':move:'+str(step),poll_menu_labels=False,
            stop_when=lambda s:s.get('interface_mode')!=1 or (s.get('player') or {}).get('life_state') in (1,2)
                or (s.get('player') or {}).get('in_combat') or (s.get('player') or {}).get('cell_id')!=state['player']['cell_id'],**kwargs)
        inputs+=1
        after=result['after'].get('player') or {}
        moved=math.dist(before[:2],after.get('position',before)[:2])
        if moving and kwargs['seconds']>=.35:
            blocked=blocked+1 if moved<20 else 0
        if blocked>=2:
            reason='Nellis course hit a physical obstacle twice; inspect or change the path.';break
    final=observer.snapshot()
    result={'action':'Follow the observed Nellis course with healing on the move','changed':inputs>0,
        'movement_attempted':True,'moved_units':round(math.dist(origin,final['player']['position']),1),
        'elapsed_seconds':round(time.monotonic()-started,2),'heals':heals,'waypoints':list(dict.fromkeys(visited)),
        'health_after':final['player'].get('health_bar_fraction_approx')}
    with (Path(__file__).parent/'course-traversals.jsonl').open('a',encoding='utf-8') as out:
        out.write(json.dumps({'at':time.time(),'request_id':request_id,'reason':reason,**result})+'\n')
    controller.history.append(result)
    return dict({'input_sent':inputs>0,'input_count':inputs,'result':result},**({'handoff':reason} if reason else {}))
