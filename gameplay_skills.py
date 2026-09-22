"""Original reusable lessons from verified New Vegas controller failures.

These are interface facts and recovery guidance, not recorded private reasoning.
Executable route/menu skills remain in their respective controller modules.
"""

def relevant_lessons(world,recent):
    lessons=[]
    if not world['disabled_controls']['movement']:
        lessons.append({'skill':'movement_during_tutorial','fact':'Movement can be available while weapon or Pip-Boy controls are disabled. Judge each control independently.'})
    failed_direct=[r for r in recent if 'directly toward' in r.get('action','') and r.get('moved_units',0)<4]
    if failed_direct:
        lessons.append({'skill':'blocked_direct_route','fact':'A direct approach made no movement. An obstacle route or manual detour can recover. A floor route may initially move away from the destination to get around a wall; judge its waypoint progress.'})
    if world.get('objectives'):
        lessons.append({'skill':'finite_actions','fact':'Actions finish before the next decision. No input continues during wait. Continue a useful route or choose another action until its objective is reached.'})
    if any(row.get('attacking_player') and row.get('alive') for row in world.get('nearby',[])):
        lessons.append({'skill':'survive_primm','fact':'The first Primm attempt died after ignoring attackers and low health. Check health, draw a weapon if holstered, and defeat close attackers or retreat to cover. A living character is required to finish the route. Use the health action to heal through the Pip-Boy.'})
    return lessons
