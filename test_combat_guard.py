import unittest
from combat_guard import restricted

class CombatGuard(unittest.TestCase):
 def test_phantom_and_misaligned_targets_cannot_enable_blind_fire(self):
  target={'shootable':True,'alive':True,'loaded':False,'distance':1000}
  self.assertNotIn('fire',restricted({'fire':''},{},{'crosshair':{'ref_id':'a'}},{'a':target}))
  target['loaded']=True
  self.assertNotIn('fire',restricted({'fire':''},{},{'crosshair':None},{'a':target}))
  self.assertIn('fire',restricted({'fire':''},{},{'crosshair':{'ref_id':'a'}},{'a':target}))
 def test_close_grenades_are_removed_but_escape_and_ranged_shots_remain(self):
  targets={x:{'shootable':True,'alive':True,'loaded':True,'distance':d} for x,d in [('close',150),('far',1000)]}
  options={x:'' for x in ('shoot:close','shoot:far','fire','vats','forward','assist')}
  r=restricted(options,{'equipped_weapon':"Mercenary's Grenade Rifle"},{'crosshair':{'ref_id':'close'}},targets)
  self.assertEqual(set(r),{'shoot:far','forward','assist'})
 def test_nonexplosive_close_combat_still_available(self):
  targets={'a':{'shootable':True,'alive':True,'loaded':True,'distance':150}}
  options={x:'' for x in ('shoot:a','fire','vats')}
  self.assertEqual(restricted(options,{'equipped_weapon':'Maria'},{'crosshair':{'ref_id':'a'}},targets),options)

if __name__=='__main__':unittest.main()
