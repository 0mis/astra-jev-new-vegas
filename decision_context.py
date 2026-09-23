"""Keep Jev's immediate judgment focused; measure loops in game outcomes."""
from collections import deque
import json,time


def scripted_observation(quest,scope,objectives):
    """This verified basement objective advances by watching a friendly demo."""
    return (quest=='Wild Card: Change in Management' and scope=='0x1221c4'
            and 'Observe upgrading of Securitrons.' in objectives)


def recent_menu_outcomes(path,pid,now=None):
    """Carry acknowledged menu actions across the menu-to-world boundary."""
    try:
        now=time.time() if now is None else now
        value=json.loads(path.read_text(encoding='utf-8'))
        if value.get('pid')!=pid or not 0<=now-value.get('updated_at',0)<600:return []
        return [{'selected':r['selected'][:240],'result':r['result'][:240]}
                for r in value.get('results',[])[-6:]
                if isinstance(r,dict) and isinstance(r.get('selected'),str) and isinstance(r.get('result'),str)]
    except (OSError,ValueError,TypeError):return []


def track_target_progress(player,targets):
    # Close-range navigation can oscillate just as distant travel can. Keep
    # nearby combat separate so standing and firing is not mistaken for travel.
    return any(t.get('quest_target') and
               (not player.get('in_combat') or t.get('distance',0)>500)
               for t in targets.values())


def door_destination(row):
    destination=row.get('destination') or {}
    if not destination:return None
    if destination.get('cell_name'):return destination['cell_name']
    if destination.get('worldspace_name'):return destination['worldspace_name']
    if destination.get('worldspace_id')=='0xda726':return 'Mojave Wasteland'
    return 'another outdoor area' if destination.get('worldspace_id') else 'another interior'


def door_activation_action(state,crosshair):
    if not crosshair or crosshair.get('kind')!=28:return None
    return next((x['text'] for m in state.get('menus',[]) if m['name']=='hud'
                 for x in m.get('labels',[]) if x.get('target')
                 and x.get('path')=='/HUDMainMenu/Info/justify_center_hotrect'
                 and x.get('text') in ('Open','Close')),None)


def actor_activation_action(state,crosshair):
    if not crosshair or crosshair.get('kind') not in (42,43):return None
    return next((x['text'] for m in state.get('menus',[]) if m['name']=='hud'
                 for x in m.get('labels',[]) if x.get('target')
                 and x.get('path')=='/HUDMainMenu/Info/justify_center_hotrect'
                 and x.get('text')=='Talk'),None)


def focus_world_context(compact,options,targets):
    advice=compact.get('planner_advice') or {}
    objectives=[o for o in compact.get('objectives',[]) if not o.lower().startswith('(optional)')]
    compact['immediate_goal']=advice.get('objective') or (objectives[0] if objectives else compact['objective'])
    player=compact.get('player_combat',{})
    hp=player.get('health_bar_fraction_approx')
    compact['health_condition']='unknown' if hp is None else 'critical' if hp<.25 else 'injured' if hp<.6 else 'healthy'
    # Keep nearby gates and obstacles, every mission target and every attacker.
    # Far unrelated actors/doors distracted healthy travel decisions in Novac.
    keep=set(targets)
    if (not player.get('in_combat') and hp is not None and hp>=.6
        and any(t.get('quest_target') for t in targets.values())):
        keep={ident for ident,t in targets.items() if t.get('quest_target') or t.get('shootable')
              or (t.get('distance') is not None and t['distance']<=250)}
    options={key:value for key,value in options.items() if ':' not in key or key.split(':',1)[1] in keep}
    compact['nearby']=[row for row in compact.get('nearby',[]) if row['id'] in keep]
    crosshair=compact.get('crosshair') or {}
    ready=targets.get(crosshair.get('ref_id'),{})
    blocked_walk=any(r.get('movement_attempted') and r.get('movement_outcome','').startswith('Walk was blocked')
                     for r in compact.get('recent_results',[])[-2:])
    blocking_door=(not player.get('in_combat') and blocked_walk
                   and crosshair.get('activation_action')=='Open'
                   and ready.get('kind')==28 and ready.get('loaded') and not ready.get('locked')
                   and any(t.get('quest_target') and t.get('distance',0)>180 for t in targets.values()))
    if crosshair.get('activation_action')=='Close':
        compact['door_recovery']='This door is already open. Walk through its opening, not into the swinging panel. If the panel blocks the approach, back away, close it once, reposition in front of the opening, then open once and allow the animation to finish. Repeated toggling is not travel.'
        for key in ('activate','interact:'+crosshair['ref_id']):
            if key in options:options[key]='Close the already open door; useful only when repositioning around a blocking swinging panel.'
    if (not player.get('in_combat') and hp is not None and hp>=.6
        and ready.get('quest_target') and ready.get('kind')==28
        and crosshair.get('activation_action')!='Close'
        and ready.get('loaded') and not ready.get('locked')
        and (ready.get('distance',float('inf'))<250 or crosshair.get('activation_action')=='Open')):
        ident=crosshair['ref_id']
        allowed={'activate','interact:'+ident,'assist'}
        available={key:value for key,value in options.items() if key in allowed}
        if any(key!='assist' for key in available):
            options=available
            compact['interaction_ready']={'target':ident,'name':ready.get('name'),
                'evidence':'The planned unlocked door is already the actual crosshair target.'}
            compact['immediate_goal']='Open the planned door '+ready.get('name','')+' now using Activate or interact. Approach is complete; do not keep walking.'
    if blocking_door:
        ident=crosshair['ref_id'];allowed={'activate','interact:'+ident,'assist'}
        options={key:value for key,value in options.items() if key in allowed}
        compact['interaction_ready']={'target':ident,'name':ready.get('name'),
            'evidence':'The last walk was blocked and the actual nearby unlocked door prompt says Open.'}
        compact['immediate_goal']='Open the door directly blocking the observed route, then continue toward the planned destination.'
    if (not player.get('in_combat') and ready.get('quest_target')
        and bool((compact.get('recent_results') or [{}])[-1].get('movement_attempted'))
        and ready.get('kind') in (42,43) and ready.get('loaded') and ready.get('alive')
        and not any(ready.get(k) for k in ('shootable','attacking_player','player_combat_target'))
        and ready.get('distance',float('inf'))<150 and crosshair.get('activation_action')=='Talk'):
        ident=crosshair['ref_id'];allowed={'activate','interact:'+ident,'assist'}
        available={key:value for key,value in options.items() if key in allowed}
        if any(key!='assist' for key in available):
            options=available
            compact['interaction_ready']={'target':ident,'name':ready.get('name'),
                'evidence':'The nearby living mission target is under the actual Talk prompt.'}
            compact['immediate_goal']='Talk to '+ready.get('name','the mission target')+' now using Activate or interact. Approach is complete.'
    compact['recent_results']=compact.get('recent_results',[])[-4:]
    compact['journal']=[row for row in compact.get('journal',[]) if row.get('active')]
    # Absolute coordinates and old skill prose aren't needed to choose an
    # available movement action. Direction/distance remain in nearby targets.
    for name in ('position','view','controls_available','controls_disabled_by_game','seconds_on_current_objective'):
        compact.pop(name,None)
    compact['reusable_skills']=compact.get('reusable_skills',[])[-3:]
    return compact,options


class ScopeProgress:
    def __init__(self):
        self.history=deque(maxlen=5);self.progress=None

    def observe(self,state,world,revision,now):
        player=state['player'];hp=player.get('health_bar_fraction_approx',0)
        # A healing trip, quest advance, new equipment, or changed plan is new
        # work. Crossing exterior grid cells does not count as changing rooms.
        progress=(tuple(o['text'] for o in world.get('objectives',[])),revision,
                  round(hp,1),player.get('equipped_weapon'))
        if progress!=self.progress:self.history.clear();self.progress=progress
        scope=world.get('worldspace_id') or player['cell_id']
        if not self.history or self.history[-1][1]!=scope:self.history.append((now,scope))
        if len(self.history)<5 or now-self.history[0][0]>90:return False
        scopes=[s for _,s in self.history]
        return scopes[0]==scopes[2]==scopes[4] and scopes[1]==scopes[3] and scopes[0]!=scopes[1]
