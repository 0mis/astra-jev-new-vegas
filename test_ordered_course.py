import unittest
from planner_destination import course_target
from world_controller import needs_floor_route
from damage_watch import nellis_artillery_traversal

class OrderedCourse(unittest.TestCase):
    def plan(self):
        return {'scope':'mojave','revision':'attempt-2','course':[
            {'ref_id':'wall','name':'Wall','kind':0,'position':[0,0,4000]},
            {'ref_id':'corner','name':'Corner','kind':0,'position':[0,1000,4000]},
            {'ref_id':'gate','name':'Gate','kind':0,'position':[1000,500,4000]}]}

    def test_turning_back_south_after_corner_does_not_reverse_course(self):
        plan=self.plan()
        _,progress=course_target(plan,'mojave',[0,0,4118],{})
        row,progress=course_target(plan,'mojave',[0,1000,4118],progress)
        self.assertEqual(row['ref_id'],'gate')
        row,_=course_target(plan,'mojave',[600,650,4118],progress)
        self.assertEqual(row['ref_id'],'gate')

    def test_wrong_floor_and_unreached_point_do_not_advance(self):
        for position in ([0,0,5000],[200,0,4118]):
            row,progress=course_target(self.plan(),'mojave',position,{})
            self.assertEqual(progress['index'],0)

    def test_wrong_scope_or_corrupt_route_is_rejected(self):
        self.assertIsNone(course_target(self.plan(),'other',[0,0,4118],{}))
        plan=self.plan();plan['course'][1]['position'][0]=float('nan')
        self.assertIsNone(course_target(plan,'mojave',[0,0,4118],{}))

    def test_new_attempt_resets_old_progress(self):
        row,progress=course_target(self.plan(),'mojave',[-500,0,4118],{'revision':'attempt-1','index':2})
        self.assertEqual(progress['index'],0)

    def test_tight_corner_keeps_target_and_movement_available_until_reached(self):
        plan=self.plan();plan['course_radius']=75
        row,progress=course_target(plan,'mojave',[110,0,4118],{})
        self.assertEqual(progress['index'],0)
        self.assertTrue(needs_floor_route(dict(row,distance=110),[110,0,4000]))
        row,progress=course_target(plan,'mojave',[70,0,4118],progress)
        self.assertEqual(progress['index'],1)

    def test_artillery_exception_requires_scoped_explicit_course(self):
        world={'quest':'Wild Card: Side Bets','worldspace_id':'0xda726'}
        player={'position':[27000,124000,4800]}
        targets={'wall':{'kind':0,'course_radius':75,'hazard':'nellis_artillery'}}
        self.assertTrue(nellis_artillery_traversal(world,player,targets))
        self.assertFalse(nellis_artillery_traversal(world,{'position':[0,0,0]},targets))
        self.assertFalse(nellis_artillery_traversal(dict(world,worldspace_id='other'),player,targets))
        self.assertFalse(nellis_artillery_traversal(world,player,{'wall':{'kind':0,'course_radius':75}}))

if __name__=='__main__':unittest.main()
