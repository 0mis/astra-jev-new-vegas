import json,tempfile,time,unittest
from pathlib import Path
from planner_destination import destination
from world_controller import reached_planner_waypoint

class WaypointHandoff(unittest.TestCase):
    def target(self,**extra):
        return dict(kind=0,ref_id='road',name='Road waypoint',position=[100,200,4300],
                    same_space=True,planner_arrival_radius=155,**extra)

    def test_actual_reached_road_hands_off(self):
        player={'position':[128,234,4316],'in_combat':False,'life_state':0}
        self.assertEqual(reached_planner_waypoint(player,{'road':self.target()})['ref_id'],'road')

    def test_partial_route_other_floor_and_combat_are_not_arrival(self):
        for player in ({'position':[800,200,4300]}, {'position':[100,200,4700]},
                       {'position':[100,200,4300],'in_combat':True}):
            self.assertIsNone(reached_planner_waypoint(player,{'road':self.target()}))
        row=self.target();row.pop('planner_arrival_radius')
        self.assertIsNone(reached_planner_waypoint({'position':[100,200,4300]},{'road':row}))

    def test_course_only_exposes_handoff_for_final_point(self):
        plan={'version':1,'expires_at':time.time()+60,'scope':'mojave','revision':'road',
              'objective_contains':'Red Rock','purpose':'Reach Red Rock','handoff_on_arrival':True,
              'course':[self.target(),dict(self.target(),ref_id='end',position=[1000,200,4300])]}
        world={'worldspace_id':'mojave','objectives':[{'text':'Go to Red Rock'}],
               'camera_view':{'yaw':0},'camera_position':[-500,200,4418]}
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'destination.json';path.write_text(json.dumps(plan))
            self.assertNotIn('planner_arrival_radius',destination(world,path))
            world['camera_position']=[100,200,4418]
            self.assertEqual(destination(world,path)['ref_id'],'end')
            self.assertEqual(destination(world,path)['planner_arrival_radius'],155)

if __name__=='__main__':unittest.main()
