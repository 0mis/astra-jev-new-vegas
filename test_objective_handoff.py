import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from planner_destination import objective_handoff
from world_controller import WorldController

class CompletedStageHandoff(unittest.TestCase):
    def setUp(self):
        self.state={'interface_mode':1,'player':{'life_state':0,'cell_id':'substation'},
                    'menus':[{'name':'hud','labels':[{'text':'HP'},{'text':'AP'}]}]}
        self.world={'quest':'Finishing Touches','objectives':[{'text':'Report back to Yes Man.'}],
                    'camera_position':[1,2,3]}
        self.plan={'version':1,'expires_at':time.time()+60,'quest':'Finishing Touches',
                   'objective_contains':'El Dorado','handoff_on_objective_change':True}
    def check(self,plan=None,state=None,world=None):
        path=Mock();path.read_text.return_value=json.dumps(self.plan if plan is None else plan)
        return objective_handoff(state or self.state,world or self.world,path)
    def test_installation_stops_old_entrance_route(self):
        self.assertIsNotNone(self.check())
        self.assertIsNone(self.check(world=dict(self.world,objectives=[{'text':'Install at El Dorado.'}])))
    def test_new_main_quest_also_hands_off(self):
        self.assertIsNotNone(self.check(world=dict(self.world,quest='No Gods, No Masters')))
    def test_only_explicit_unexpired_stage_plans(self):
        self.assertIsNone(self.check(plan=dict(self.plan,handoff_on_objective_change=False)))
        self.assertIsNone(self.check(plan=dict(self.plan,expires_at=0)))
        self.assertIsNone(self.check(plan=dict(self.plan,objective_contains='')))
    def test_loading_and_terminal_screens_are_not_stage_changes(self):
        self.assertIsNone(self.check(state=dict(self.state,interface_mode=2)))
        for changes in ({'objectives':[]},{'quest':None},{'objectives':[{}]}):
            self.assertIsNone(self.check(world=dict(self.world,**changes)))
        self.assertIsNone(self.check(state=dict(self.state,player={'life_state':2})))
    def test_handoff_precedes_target_selection_and_new_model_call(self):
        with tempfile.TemporaryDirectory() as folder,patch('planner_destination.ROOT',Path(folder)):
            Path(folder,'planner-destination.json').write_text(json.dumps(self.plan))
            controller=WorldController.__new__(WorldController)
            controller.planner=Mock();controller.targets=Mock(side_effect=AssertionError('Old target chosen'))
            observer=Mock();observer.world.return_value=self.world;client=Mock()
            result=controller._step(observer,client,123,Path('recording'),self.state)
            self.assertFalse(result['input_sent']);self.assertIn('handoff',result)
            controller.targets.assert_not_called();client.request.assert_not_called()
            controller.planner.request_help.assert_called_once()

if __name__=='__main__':unittest.main()
