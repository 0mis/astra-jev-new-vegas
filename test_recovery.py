"""Regression checks for the observed status-file and wall-loop failures."""
import json
import pathlib
import tempfile
import unittest
from collections import deque
from unittest.mock import patch

from planner_mailbox import atomic_json
from world_controller import WorldController
from navmesh import Mesh,corridor_visible,corridor_clearance,region_fraction
from decide_game import capture_quality


class StatusPublication(unittest.TestCase):
    def test_locked_replace_never_truncates_previous_status(self):
        with tempfile.TemporaryDirectory() as folder:
            target=pathlib.Path(folder)/'status.json'
            target.write_text('{"state":"previous"}')
            with patch.object(pathlib.Path,'replace',side_effect=PermissionError('busy reader')), patch('planner_mailbox.time.sleep'):
                self.assertFalse(atomic_json(target,{'state':'next'},best_effort=True))
            self.assertEqual(json.loads(target.read_text()),{'state':'previous'})
            self.assertTrue(atomic_json(target,{'state':'next'}))
            self.assertEqual(json.loads(target.read_text()),{'state':'next'})

    def test_short_lock_is_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            target=pathlib.Path(folder)/'status.json'
            real_replace=pathlib.Path.replace
            attempts=[]
            def replace(source,dest):
                attempts.append(1)
                if len(attempts)<3:raise PermissionError('busy reader')
                return real_replace(source,dest)
            with patch.object(pathlib.Path,'replace',replace), patch('planner_mailbox.time.sleep'):
                self.assertTrue(atomic_json(target,{'state':'ready'}))
            self.assertEqual(json.loads(target.read_text()),{'state':'ready'})

class CaptureQuality(unittest.TestCase):
    def test_isolated_logged_warning_does_not_stop_fresh_synchronized_capture(self):
        state={'audio_discontinuities':1,'audio_warnings':[{'at':95,'message':'data discontinuity'}]}
        self.assertEqual(capture_quality(state,10_000_000,10_100_000,100)['audio_warning_count'],1)

    def test_persistent_glitches_stop_capture_use(self):
        state={'audio_warnings':[{'at':t,'message':'data discontinuity'} for t in [80,90,95]]}
        with self.assertRaises(RuntimeError):capture_quality(state,10_000_000,10_000_000,100)

    def test_timeline_drift_stops_capture_use(self):
        with self.assertRaises(RuntimeError):capture_quality({},10_000_000,7_000_000,100)


class TravelRecovery(unittest.TestCase):
    def setUp(self):
        self.controller=WorldController.__new__(WorldController)
        self.controller.travel_samples=deque()
        self.world={'objectives':[{'text':'Reach the casino'}]}

    def sample(self,seconds,x,cell='exterior'):
        return self.controller.travel_stalled({'player':{'cell_id':cell,'position':[x,0,0]}},self.world,seconds)

    def test_collision_slide_and_return_is_a_stall(self):
        for t in range(40):
            self.assertFalse(self.sample(t,120 if t%2 else 0))
        self.assertTrue(self.sample(40,0))

    def test_forward_travel_is_not_a_stall(self):
        for t in range(100):self.assertFalse(self.sample(t,t*250))

    def test_cell_transition_resets_the_window(self):
        for t in range(40):self.sample(t,0)
        self.assertFalse(self.sample(40,0,'interior'))

    def test_exterior_cell_oscillation_remains_a_stall(self):
        self.world['worldspace_id']='same-wasteland'
        for t in range(40):self.sample(t,120 if t%2 else 0,'a' if t%2 else 'b')
        self.assertTrue(self.sample(40,0,'b'))

    def test_ineffective_route_stays_unavailable(self):
        self.controller.tick=5;self.controller.cooldowns={'route:casino':10}
        world={'disabled_controls':dict.fromkeys(('movement','look','fight','pipboy','sneak','point_of_view'),False)}
        choices=self.controller.options(world,{'casino':{'name':'Casino','distance':4300,'quest_target':True}})
        self.assertNotIn('route:casino',choices)
        self.assertIn('assist',choices)
        self.assertIn('left',choices)

    def test_exterior_boundary_preserves_the_current_route(self):
        self.assert_route_transition(0x300,False)

    def test_interior_transition_discards_exterior_coordinates(self):
        self.assert_route_transition(0,True)

    def assert_route_transition(self,space,should_clear):
        c=self.controller;c.mesh_space='0x123';c.mesh_cell='old';c.route_for=('door',());c.route_points=[(1,2,3)]
        class ObservedPointers:
            def u32(self,address):return {0x11DEA3C:0x100,0x140:0x200,0x2C0:space,0x30C:0x123}[address]
        with patch('navmesh.Mesh') as mesh:
            mesh.return_value.mesh_count=1;mesh.return_value.cell_count=1;mesh.return_value.declared_links=1
            c.ensure_mesh(ObservedPointers(),{'player':{'cell_id':'new'}})
        self.assertEqual(c.route_points,[] if should_clear else [(1,2,3)])


class CrossCellRoutes(unittest.TestCase):
    def make_mesh(self,gap=6,linked=True):
        mesh=Mesh.__new__(Mesh)
        mesh.triangles=[((0,0,0),(100,0,0),(0,100,0)),
                        ((100+gap,0,0),(100+gap,100,0),(gap,100,0))]
        mesh.edges=[set(),set()];mesh.portals={}
        mesh.centers=[tuple(sum(v[k] for v in t)/3 for k in range(3)) for t in mesh.triangles]
        data={10:{'offset':0,'records':[(0,1,2,-1,0,-1,2 if linked else 0)],'links':[(20,0)]},
              20:{'offset':1,'records':[(0,1,2,-1,-1,-1,0)],'links':[]}}
        mesh.connect_declared_links(data)
        return mesh

    def test_declared_boundary_with_offset_connects(self):
        mesh=self.make_mesh()
        self.assertEqual(mesh.route((5,5,0),(95,95,0)),[0,1])
        self.assertEqual(mesh.portals[0,1],(50,50,0))

    def test_nearby_undeclared_surfaces_are_not_connected(self):
        self.assertFalse(self.make_mesh(linked=False).edges[0])

    def test_invalid_large_gap_is_not_connected(self):
        self.assertFalse(self.make_mesh(gap=300).edges[0])

    def test_shortcut_needs_clearance_beyond_center_line(self):
        floor=[((0,0,0),(100,0,0),(0,200,0)),((100,0,0),(100,200,0),(0,200,0))]
        self.assertTrue(corridor_visible((10,30,0),(10,170,0),floor))
        self.assertFalse(corridor_clearance((10,30,0),(10,170,0),floor))
        self.assertTrue(corridor_clearance((50,30,0),(50,170,0),floor))

    def test_observed_region_penalizes_crossing_but_not_parallel_escape(self):
        bounds=[20,20,80,80]
        self.assertAlmostEqual(region_fraction((0,50,0),(100,50,0),bounds),.6)
        self.assertEqual(region_fraction((0,0,0),(100,0,0),bounds),0)
        self.assertAlmostEqual(region_fraction((50,50,0),(150,50,0),bounds),.3)


if __name__=='__main__':unittest.main()
