import time,unittest
from pathlib import Path
from unittest.mock import Mock
from planner_mailbox import restrict_world_options,validated_advice
from world_controller import WorldController

class EscapeGuard(unittest.TestCase):
 def test_valid_escape_retains_survival_and_travel_without_attacks(self):
  advice=validated_advice({'version':1,'stage':'a','expires_at':time.time()+60,'objective':'Escape','avoid_combat':True},'a')
  options={k:k for k in ['fire','vats','shoot:enemy','route:exit','health','quick_heal','assist','interact:exit','holster']}
  filtered=restrict_world_options(options,advice)
  self.assertEqual(set(filtered),{'route:exit','health','quick_heal','assist','interact:exit','holster'})
 def test_absent_false_expired_and_wrong_stage_do_not_restrict(self):
  options={'fire':'shoot','route:exit':'run'}
  for advice in (None,{}, {'avoid_combat':False},{'avoid_combat':'true'}):self.assertEqual(restrict_world_options(options,advice),options)
  for change in ({'expires_at':0},{'stage':'b'}):
   advice=validated_advice(dict({'version':1,'stage':'a','expires_at':time.time()+60,'objective':'Escape','avoid_combat':True},**change),'a')
   self.assertEqual(restrict_world_options(options,advice),options)
 def test_critical_health_handoff_precedes_any_new_decision_or_target(self):
  state={'interface_mode':1,'player':{'life_state':0,'cell_id':'tower','health_bar_fraction_approx':.04},'menus':[{'name':'hud','labels':[{'text':'HP'},{'text':'AP'}]}]}
  world={'camera_position':[0,0,0]}
  controller=WorldController.__new__(WorldController);controller.planner=Mock();controller.targets=Mock(side_effect=AssertionError('Target selected at critical HP'))
  observer=Mock();observer.world.return_value=world;client=Mock()
  result=controller._step(observer,client,123,Path('recording'),state)
  self.assertTrue(result['critical_health_observed']);self.assertFalse(result['input_sent'])
  controller.targets.assert_not_called();client.request.assert_not_called()

if __name__=='__main__':unittest.main()
