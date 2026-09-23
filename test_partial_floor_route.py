import unittest
from world_controller import partial_floor_route,WorldController

class Floor:
    triangles=[[(0,0,4300),(500,0,4300),(0,500,4300)]]
    centers=[(500/3,500/3,4300)]
    def nearest(self,point,ignore_height=False):return 0

class PartialFloorRoute(unittest.TestCase):
    def test_nearest_loaded_floor_does_not_prove_distant_arrival(self):
        self.assertTrue(partial_floor_route(Floor(),[0],{'kind':0,'position':[10000,100,4300]}))

    def test_destination_inside_floor_is_complete_even_far_from_centroid(self):
        self.assertFalse(partial_floor_route(Floor(),[0],{'kind':0,'position':[450,20,4300]}))

    def test_height_only_ignored_for_flat_map_marker(self):
        self.assertTrue(partial_floor_route(Floor(),[0],{'kind':28,'position':[100,100,4800]}))
        self.assertFalse(partial_floor_route(Floor(),[0],{'kind':0,'position':[100,100,0]}))

    def test_direct_recovery_step_drops_old_corridor_but_facing_does_not(self):
        controller=WorldController.__new__(WorldController)
        controller.calibration={'yaw_per_dx':.001,'pitch_per_dy':.001}
        controller.route_for=('road',);controller.route_points=[[0,-500,4300]];controller.route_partial=True
        state={'player':{'position':[0,0,4300],'run_speed':300}}
        world={'camera_position':[0,0,4418],'camera_view':{'yaw':0,'pitch':0}}
        target={'kind':0,'position':[0,1000,4300],'distance':1000}
        controller.target_input(None,state,world,target,'face')
        self.assertEqual(controller.route_points,[[0,-500,4300]])
        action=controller.target_input(None,state,world,target,'direct')
        self.assertEqual(action['keys'],['w'])
        self.assertIsNone(controller.route_for)
        self.assertEqual(controller.route_points,[])

if __name__=='__main__':unittest.main()
