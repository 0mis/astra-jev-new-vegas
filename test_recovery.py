"""Regression checks for the observed status-file and wall-loop failures."""
import json
import pathlib
import tempfile
import unittest
from collections import deque
from unittest.mock import patch

from planner_mailbox import atomic_json
from world_controller import WorldController
from navmesh import Mesh,corridor_visible,corridor_clearance,region_fraction,triangle_distance
from decide_game import capture_quality
from record_game import write_state


class StatusPublication(unittest.TestCase):
    def test_recorder_survives_lock_longer_than_previous_retry_window(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=pathlib.Path(folder)
            target=directory/'session.json'
            target.write_text('{"state":"previous"}')
            original=pathlib.Path.replace
            attempts=[]
            def replace(source,dest):
                attempts.append(1)
                if len(attempts)<=5:
                    self.assertEqual(json.loads(target.read_text()),{'state':'previous'})
                    raise PermissionError('busy reader')
                return original(source,dest)
            with patch.object(pathlib.Path,'replace',replace), patch('record_game.time.sleep'):
                write_state(directory,{'state':'recording'})
            self.assertEqual(json.loads(target.read_text()),{'state':'recording'})

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
    def test_flat_map_target_does_not_prefer_unrelated_lower_floor(self):
        mesh=Mesh.__new__(Mesh)
        mesh.triangles=[((0,0,100),(20,0,100),(0,20,100)),
                        ((70,0,5),(90,0,5),(70,20,5))]
        mesh.centers=[tuple(sum(v[k] for v in t)/3 for k in range(3)) for t in mesh.triangles]
        mesh.edges=[{1},{0}]
        self.assertEqual(mesh.nearest((5,5,100)),0)
        self.assertEqual(mesh.route((5,5,100),(5,5,0),flat_target=True),[0])

    def test_collapsed_floor_cannot_capture_distant_destination(self):
        collapsed=((0,0,0),(0,0,1),(0,0,2))
        self.assertAlmostEqual(triangle_distance((300,400,0),collapsed),500)
        collinear=((0,0,0),(10,0,0),(20,0,0))
        self.assertAlmostEqual(triangle_distance((100,0,0),collinear),80)
        mesh=Mesh.__new__(Mesh)
        mesh.triangles=[collapsed,((290,390,0),(340,390,0),(290,440,0))]
        mesh.centers=[tuple(sum(v[k] for v in t)/3 for k in range(3)) for t in mesh.triangles]
        self.assertEqual(mesh.nearest((300,400,0)),1)

    def test_declared_internal_link_survives_three_overlapping_edges(self):
        mesh=Mesh.__new__(Mesh)
        mesh.triangles=[((0,0,0),(100,0,0),(0,100,0)),
                        ((100,0,0),(100,100,0),(0,100,0)),
                        ((100,0,0),(100,100,0),(0,100,0))]
        mesh.edges=[set(),set(),set()];mesh.portals={}
        records=[(0,1,2,-1,1,-1,0),(0,1,2,-1,-1,-1,0),(0,1,2,-1,-1,-1,0)]
        self.assertEqual(mesh.connect_internal_links({1:{'offset':0,'records':records}}),1)
        self.assertEqual(mesh.edges[0],{1})
        self.assertEqual(mesh.edges[2],set())

    def test_internal_link_rejects_nonmatching_geometry(self):
        mesh=Mesh.__new__(Mesh)
        mesh.triangles=[((0,0,0),(100,0,0),(0,100,0)),((500,0,0),(600,0,0),(500,100,0))]
        mesh.edges=[set(),set()];mesh.portals={}
        self.assertEqual(mesh.connect_internal_links({1:{'offset':0,'records':[(0,1,2,-1,1,-1,0),(0,1,2,-1,-1,-1,0)]}}),0)

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


class MainStoryTargets(unittest.TestCase):
    def test_optional_exterior_lead_does_not_promote_room_exit(self):
        from unittest.mock import Mock
        controller=WorldController.__new__(WorldController);controller.travel_memory=Mock()
        exit_door={'ref_id':'exit','name':'Door','kind':28,'distance':57,'same_space':True,'loaded':True,'destination':{'cell_name':'Mojave Wasteland'}}
        beagle={'ref_id':'beagle','name':'Deputy Beagle','kind':42,'distance':4500,'same_space':True,'loaded':True}
        victor={'ref_id':'victor','name':'Victor','kind':43,'distance':45000,'same_space':False,'loaded':False}
        controller.travel_memory.entrances.return_value=[exit_door]
        world={'objectives':[{'text':'Find Primm lawman','targets':[beagle]},{'text':'(Optional) Talk to Victor','targets':[victor]}],'nearby':[exit_door]}
        targets=controller.targets(world)
        self.assertTrue(targets['beagle']['quest_target'])
        self.assertFalse(targets['exit']['quest_target'])
        self.assertNotIn('victor',targets)
        exit_door['locked']=True
        self.assertIn('exit',controller.targets(world))
        exit_door['locked']=False
        beagle['same_space']=False;victor['same_space']=True
        targets=controller.targets(world)
        self.assertTrue(targets['exit']['quest_target'])
        self.assertNotIn('victor',targets)

class HealingDecisionWindow(unittest.TestCase):
    def test_stale_highlight_is_not_safe_to_activate(self):
        from equipment_controller import activation_ready
        self.assertFalse(activation_ready('Super Stimpak (2)',None,True))
        self.assertFalse(activation_ready('Super Stimpak (2)',{'name':'Super Stimpak'},False))
        self.assertFalse(activation_ready('Super Stimpak (2)',{'name':"Doctor's Bag"},True))
        self.assertTrue(activation_ready('Super Stimpak (2)',{'name':'Super Stimpak'},True))

    def test_inventory_health_is_not_carried_weight(self):
        from equipment_controller import health_from_text
        self.assertEqual(health_from_text(['97/200','Wg','15/240','HP']),{'current':15,'maximum':240})
        self.assertIsNone(health_from_text(['97/200','Wg','HP']))

    def test_critical_aid_prioritizes_hit_points_over_limb_repair(self):
        from equipment_controller import survival_choices
        choices={'use:0':'Use Super Stimpak to restore hit points;',
                 'use:1':'Use Doctors Bag to repair injured limbs (does not restore hit points)',
                 'close':'Close','assist':'Ask Astra'}
        self.assertEqual(set(survival_choices(choices,{'current':15,'maximum':240},True,2)),{'use:0','assist'})
        self.assertEqual(survival_choices(choices,{'current':220,'maximum':240},True,2),choices)

    def test_no_healing_supply_does_not_trap_inventory(self):
        from equipment_controller import survival_choices
        choices={'close':'Close','assist':'Ask Astra'}
        self.assertEqual(survival_choices(choices,{'current':15,'maximum':240},True,2),choices)
        choices['equip:4']='Equip caravan shotgun';choices['tab:2']='Show Aid'
        self.assertEqual(survival_choices(choices,{'current':15,'maximum':240},True,0,False),choices)

    def test_ongoing_fight_does_not_close_at_half_health(self):
        from pipboy_controller import needs_more_healing
        self.assertTrue(needs_more_healing({'current':130,'maximum':240},True))
        self.assertFalse(needs_more_healing({'current':193,'maximum':240},True))
        self.assertFalse(needs_more_healing({'current':130,'maximum':240},False))
        self.assertTrue(needs_more_healing({'current':99,'maximum':240},False))

class CameraTransitions(unittest.TestCase):
    def test_vats_animation_does_not_dispatch_world_inputs(self):
        from unittest.mock import Mock
        controller=WorldController.__new__(WorldController)
        observer,client=Mock(),Mock()
        with patch('world_controller.time.sleep'):
            result=controller.step(observer,client,1,'capture',{'vats_mode':2})
        self.assertTrue(result['waiting_for_vats_execution'])
        observer.world.assert_not_called()
        client.request.assert_not_called()

class CampaignCheckpoints(unittest.TestCase):
    def test_cell_transition_discards_observation_without_replaying(self):
        from unittest.mock import Mock
        controller=WorldController.__new__(WorldController)
        observer=Mock();observer.world.side_effect=RuntimeError('World changed during observation')
        client=Mock()
        with patch('world_controller.act') as send:
            result=controller.step(observer,client,1,'capture',{'player':{'life_state':0}})
            self.assertIn('observation_discarded',result)
            send.assert_not_called();client.request.assert_not_called()
        observer.world.side_effect=RuntimeError('Unrelated failure')
        with self.assertRaisesRegex(RuntimeError,'Unrelated failure'):
            controller.step(observer,client,1,'capture',{'player':{'life_state':0}})

    def test_death_injury_and_animation_never_replace_good_progress(self):
        from campaign_checkpoint import should_checkpoint
        state={'interface_mode':1,'vats_mode':0,'player':{'life_state':0,'health_bar_fraction_approx':.8},
               'menus':[{'name':'hud','labels':[{'text':'HP'},{'text':'AP'}]}]}
        self.assertTrue(should_checkpoint(state,{},None,100))
        # Safe partial-health progress is useful; immutable older saves remain.
        state['player']['health_bar_fraction_approx']=.413
        self.assertTrue(should_checkpoint(state,{},None,100))
        state['player']['in_combat']=True
        self.assertFalse(should_checkpoint(state,{},None,100))
        state['player']['in_combat']=False
        state['player']['life_state']=1
        self.assertFalse(should_checkpoint(state,{},None,100))
        state['player']['life_state']=0;state['player']['health_bar_fraction_approx']=.05
        self.assertFalse(should_checkpoint(state,{},None,100))
        state['player']['health_bar_fraction_approx']=.8;state['vats_mode']=2
        self.assertFalse(should_checkpoint(state,{},None,100))

    def test_missing_camera_never_dispatches_a_decision(self):
        from unittest.mock import Mock
        controller=WorldController.__new__(WorldController)
        observer=Mock();observer.world.return_value={'camera_position':None}
        client=Mock()
        with patch('world_controller.time.sleep'):
            result=controller.step(observer,client,1,'capture',{'player':{'life_state':0}})
        self.assertIn('discarded',result)
        client.request.assert_not_called()

    def test_sustained_missing_camera_hands_back_control(self):
        from unittest.mock import Mock
        controller=WorldController.__new__(WorldController);controller.camera_missing_since=10
        observer=Mock();observer.world.return_value={'camera_position':None}
        client=Mock()
        with patch('world_controller.time.monotonic',return_value=16):
            result=controller.step(observer,client,1,'capture',{'player':{'life_state':0}})
        self.assertIn('handoff',result)
        client.request.assert_not_called()

class NetworkRecovery(unittest.TestCase):
    def test_new_destination_does_not_inherit_time_spent_looting(self):
        controller=WorldController.__new__(WorldController);controller.travel_samples=deque()
        state={'player':{'cell_id':'outside','position':[10,0,0]}}
        world={'objectives':[{'text':'Reach Novac'}]}
        self.assertFalse(controller.travel_stalled(state,world,0,['corpse']))
        self.assertFalse(controller.travel_stalled(state,world,60,['town']))
        self.assertEqual(len(controller.travel_samples),1)

    def test_resume_requires_fresh_verified_pause_capture_and_same_campaign(self):
        from jev_loop import network_recovery_allowed
        status={'pid':1,'recording':'capture','state':'stopped','reason':'TimeoutError: The read operation timed out',
                'updated_at':100,'handoff_pause':{'verified_paused':True}}
        state={'pid':1,'player':{'life_state':0},'menus':[{'name':'start','labels':[{'text':'Continue'}]}]}
        health={'healthy':True,'game_pid':1}
        self.assertTrue(network_recovery_allowed(status,state,health,1,'capture',101))
        self.assertFalse(network_recovery_allowed(status,state,health,1,'capture',111))
        self.assertFalse(network_recovery_allowed(status,state,health,1,'capture',101,True))
        self.assertFalse(network_recovery_allowed(status,state,health,1,'other-campaign',101))
        self.assertFalse(network_recovery_allowed(status,state,{'healthy':False},1,'capture',101))
        state['menus']=[{'name':'hud','labels':[]}]
        self.assertFalse(network_recovery_allowed(status,state,health,1,'capture',101))

if __name__=='__main__':unittest.main()
