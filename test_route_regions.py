import unittest
from planner_destination import scoped_target


class StreetPartitions(unittest.TestCase):
    def plan(self):
        return {'regions':[
            {'scope':'strip','bounds_xy':[-10000,4900,10000,15000],'target':{'ref_id':'inner-gate'}},
            {'scope':'strip','bounds_xy':[-10000,-10000,10000,4900],'target':{'ref_id':'tops'}}],
            'targets_by_scope':{'shop':{'ref_id':'exit'}}}

    def test_gate_transition_changes_target_even_with_same_worldspace(self):
        plan=self.plan()
        self.assertEqual(scoped_target(plan,'strip',[-36,5284,1010])['ref_id'],'inner-gate')
        self.assertEqual(scoped_target(plan,'strip',[-33,4656,1011])['ref_id'],'tops')

    def test_coordinate_overlap_does_not_cross_scope(self):
        self.assertIsNone(scoped_target(self.plan(),'mojave',[-36,5284,1010]))
        self.assertEqual(scoped_target(self.plan(),'shop',[-36,5284,1010])['ref_id'],'exit')

    def test_invalid_region_fails_closed(self):
        plan=self.plan();plan['regions'][0]['bounds_xy']=[0,0,0,1]
        self.assertIsNone(scoped_target(plan,'strip',[-36,5284,1010]))


if __name__=='__main__':unittest.main()
