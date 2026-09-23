"""Avoid blind fire and close-range grenade self-damage in ordinary combat."""
def ranged_grenade(player):
 return 'grenade rifle' in player.get('equipped_weapon','').lower()

def restricted(options,player,world,targets):
 result=dict(options)
 aimed=targets.get((world.get('crosshair') or {}).get('ref_id'))
 if not aimed or not aimed.get('shootable') or not aimed.get('alive') or not aimed.get('loaded'):
  result.pop('fire',None)
 if ranged_grenade(player):
  for ident,t in targets.items():
   if t.get('distance') is None or t['distance']<600:result.pop('shoot:'+ident,None)
  if not aimed or aimed.get('distance') is None or aimed['distance']<600:result.pop('fire',None)
  if any(t.get('shootable') and t.get('alive') and t.get('distance') is not None and t['distance']<600 for t in targets.values()):result.pop('vats',None)
 return result
