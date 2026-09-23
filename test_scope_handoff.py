import json,unittest
from unittest.mock import Mock
from planner_destination import scope_handoff

class DoorwayHandoff(unittest.TestCase):
    def setUp(self):
        self.state={'interface_mode':1,'player':{'life_state':0,'cell_id':'interior'}}
        self.world={'quest':'Finishing','worldspace_id':'outside','objectives':[{'text':'Install the chip'}]}
        self.plan={'version':1,'expires_at':100,'quest':'Finishing','objective_contains':'Install','handoff_scopes':['outside']}
    def check(self,plan=None,state=None,world=None):
        path=Mock();path.read_text.return_value=json.dumps(self.plan if plan is None else plan)
        return scope_handoff(state or self.state,world or self.world,path,50)
    def test_handoff_only_after_the_requested_transition(self):
        self.assertIsNotNone(self.check())
        self.assertIsNone(self.check(world=dict(self.world,worldspace_id='interior')))
        self.assertIsNone(self.check(plan=dict(self.plan,handoff_scopes=[])))
    def test_old_plan_and_new_objective_cannot_stop_current_travel(self):
        self.assertIsNone(self.check(plan=dict(self.plan,expires_at=49)))
        self.assertIsNone(self.check(world=dict(self.world,quest='Another quest')))
        self.assertIsNone(self.check(world=dict(self.world,objectives=[{'text':'Return to the casino'}])))
    def test_does_not_replace_combat_or_death_handling(self):
        for change in ({'life_state':2},{'in_combat':True}):
            self.assertIsNone(self.check(state=dict(self.state,player=dict(self.state['player'],**change))))
        self.assertIsNone(self.check(state=dict(self.state,interface_mode=2)))

if __name__=='__main__':unittest.main()
