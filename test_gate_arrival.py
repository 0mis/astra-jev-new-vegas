import unittest
from collections import deque
from decision_context import focus_world_context,track_target_progress,door_activation_action,actor_activation_action
from world_controller import WorldController


class GateArrival(unittest.TestCase):
    def test_loaded_intercom_exposes_normal_interaction(self):
        controller=WorldController.__new__(WorldController)
        controller.cooldowns={};controller.tick=0
        target={'ref_id':'intercom','name':'Intercom','kind':22,'position':[50,0,0],
                'loaded':True,'distance':50,'quest_target':True}
        world={'objectives':[],'quest':None,'worldspace_id':None,'cell_id':'bunker',
               'camera_position':[0,0,0],'disabled_controls':{k:False for k in
               ('movement','look','fight','pipboy','sneak','point_of_view')}}
        self.assertIn('interact:intercom',controller.options(world,{'intercom':target}))
        target['loaded']=False
        self.assertNotIn('interact:intercom',controller.options(world,{'intercom':target}))

    def test_blocking_fence_gate_uses_actual_open_prompt_despite_remote_pivot(self):
        compact,targets,options=self.fixture()
        compact['crosshair']['activation_action']='Open'
        compact['recent_results']=[{'movement_attempted':True,'movement_outcome':'Walk was blocked'}]
        targets['gate'].update(quest_target=False,distance=544.6)
        targets['pass']={'quest_target':True,'distance':2885.6}
        focused,choices=focus_world_context(compact,options,targets)
        self.assertEqual(set(choices),{'activate','assist'})
        targets['gate']['loaded']=False
        self.assertIn('forward',focus_world_context(compact,options,targets)[1])

    def test_yes_man_arrival_talks_instead_of_walking_into_him(self):
        compact,targets,options=self.fixture()
        targets['gate'].update(kind=43,name='Yes Man',alive=True,distance=74.6)
        compact['crosshair']['activation_action']='Talk'
        compact['recent_results']=[{'movement_attempted':True}]
        focused,choices=focus_world_context(compact,options,targets)
        self.assertEqual(set(choices),{'activate','interact:gate','assist'})
        self.assertIn('Talk to Yes Man',focused['immediate_goal'])

    def test_talk_arrival_does_not_override_combat_or_missing_evidence(self):
        for changed in ('in_combat','shootable','attacking_player','player_combat_target','alive','loaded','quest_target','distance','prompt'):
            compact,targets,options=self.fixture()
            targets['gate'].update(kind=43,name='Yes Man',alive=True,distance=74.6)
            compact['crosshair']['activation_action']='Talk'
            compact['recent_results']=[{'movement_attempted':True}]
            if changed=='in_combat':compact['player_combat']['in_combat']=True
            elif changed=='prompt':compact['crosshair']['activation_action']=None
            elif changed=='distance':targets['gate']['distance']=160
            else:targets['gate'][changed]=changed in ('shootable','attacking_player','player_combat_target')
            self.assertIn('forward',focus_world_context(compact,options,targets)[1],changed)

    def test_conversation_return_keeps_departure_controls_and_planner_goal(self):
        compact,targets,options=self.fixture()
        targets['gate'].update(kind=42,name='Mortimer',alive=True,distance=75)
        compact['crosshair']['activation_action']='Talk'
        compact['recent_results']=[{'movement_attempted':True},{'transition':True,'menus':['hud','dialogue']}]
        compact['planner_advice']={'objective':'Leave the exhausted conversation and meet Marjorie.'}
        focused,choices=focus_world_context(compact,options,targets)
        self.assertIn('forward',choices)
        self.assertEqual(focused['immediate_goal'],compact['planner_advice']['objective'])

    def test_talk_prompt_requires_actual_hud_activation_control(self):
        state={'menus':[{'name':'hud','labels':[
            {'text':'Talk','target':1,'path':'/unrelated'},
            {'text':'Talk','target':1,'path':'/HUDMainMenu/Info/justify_center_hotrect'}]}]}
        self.assertEqual(actor_activation_action(state,{'kind':43}),'Talk')
        state['menus'][0]['labels'].pop()
        self.assertIsNone(actor_activation_action(state,{'kind':43}))
        self.assertIsNone(actor_activation_action(state,{'kind':28}))

    def test_injured_bed_route_opens_actual_blocking_door(self):
        compact,targets,options=self.fixture()
        compact['player_combat']['health_bar_fraction_approx']=.253
        compact['crosshair']['activation_action']='Open'
        compact['recent_results']=[{'movement_attempted':True,'movement_outcome':'Walk was blocked; use a different local approach.'}]
        targets['gate'].update(quest_target=False,distance=52.8)
        targets['bed']={'quest_target':True,'distance':682.8}
        focused,choices=focus_world_context(compact,options,targets)
        self.assertEqual(set(choices),{'activate','interact:gate','assist'})
        self.assertIn('blocking',focused['immediate_goal'])

    def test_blocked_route_never_forces_closed_door_recovery_in_combat(self):
        compact,targets,options=self.fixture()
        compact['player_combat']['in_combat']=True
        compact['crosshair']['activation_action']='Open'
        compact['recent_results']=[{'movement_attempted':True,'movement_outcome':'Walk was blocked'}]
        targets['gate'].update(quest_target=False,distance=52.8)
        targets['bed']={'quest_target':True,'distance':682.8}
        self.assertIn('forward',focus_world_context(compact,options,targets)[1])

    def test_open_door_keeps_travel_and_does_not_force_close(self):
        compact,targets,options=self.fixture()
        compact['crosshair']['activation_action']='Close'
        focused,choices=focus_world_context(compact,options,targets)
        self.assertIn('forward',choices)
        self.assertNotIn('interaction_ready',focused)
        self.assertIn('already open',choices['activate'])

    def test_door_verb_comes_from_actual_crosshair_prompt_not_other_hud_text(self):
        state={'menus':[{'name':'hud','labels':[
            {'text':'Close','target':1,'path':'/unrelated'},
            {'text':'Open','target':1,'path':'/HUDMainMenu/Info/justify_center_hotrect'}]}]}
        self.assertEqual(door_activation_action(state,{'kind':28}),'Open')
        self.assertIsNone(door_activation_action(state,{'kind':42}))
        self.assertIsNone(door_activation_action(state,None))

    def fixture(self):
        compact={'objective':'Leave Freeside','objectives':['Confront Benny'],
            'player_combat':{'in_combat':False,'health_bar_fraction_approx':1},
            'crosshair':{'ref_id':'gate'},'nearby':[{'id':'gate'}]}
        targets={'gate':{'ref_id':'gate','name':'East Gate','kind':28,
            'quest_target':True,'loaded':True,'locked':False,'distance':133.8}}
        options={'activate':'E','interact:gate':'Verified interaction','forward':'W','assist':'Help'}
        return compact,targets,options

    def test_actual_gate_crosshair_ends_approach_even_with_offset_pivot(self):
        compact,targets,options=self.fixture()
        focused,choices=focus_world_context(compact,options,targets)
        self.assertEqual(set(choices),{'activate','interact:gate','assist'})
        self.assertEqual(focused['interaction_ready']['target'],'gate')

    def test_lucky38_remote_pivot_uses_actual_open_prompt(self):
        compact,targets,options=self.fixture()
        targets['gate']['distance']=1100
        compact['crosshair']['activation_action']='Open'
        focused,choices=focus_world_context(compact,options,targets)
        self.assertEqual(set(choices),{'activate','interact:gate','assist'})
        compact,targets,options=self.fixture()
        targets['gate']['distance']=1100
        self.assertIn('forward',focus_world_context(compact,options,targets)[1])

    def test_no_arrival_claim_for_wrong_crosshair_locked_or_unloaded_door(self):
        for changed in ('crosshair','locked','loaded','quest_target'):
            compact,targets,options=self.fixture()
            if changed=='crosshair':compact['crosshair']={'ref_id':'another'}
            else:targets['gate'][changed]=changed=='locked'
            self.assertIn('forward',focus_world_context(compact,options,targets)[1])

    def test_injury_and_combat_keep_escape_controls(self):
        for state in ({'in_combat':True,'health_bar_fraction_approx':1},
                      {'in_combat':False,'health_bar_fraction_approx':.3}):
            compact,targets,options=self.fixture();compact['player_combat']=state
            self.assertIn('forward',focus_world_context(compact,options,targets)[1])

    def test_ready_interaction_does_not_move_or_activate_twice(self):
        controller=WorldController.__new__(WorldController)
        result=controller.target_input(None,{}, {'crosshair':{'ref_id':'gate'}},
                                       {'ref_id':'gate'},'interact')
        self.assertFalse(any(result.get(key) for key in ('keys','dx','dy','button')))

    def test_nearby_noncombat_goal_remains_monitored(self):
        _,targets,_=self.fixture()
        self.assertTrue(track_target_progress({'in_combat':False},targets))
        self.assertFalse(track_target_progress({'in_combat':True},targets))
        targets['gate']['distance']=700
        self.assertTrue(track_target_progress({'in_combat':True},targets))

    def test_observed_gate_oscillation_triggers_without_crossing_cells(self):
        controller=WorldController.__new__(WorldController);controller.travel_samples=deque()
        world={'worldspace_id':'freeside','objectives':[{'text':'Leave through gate'}]}
        for i in range(15):
            state={'player':{'cell_id':'same-grid','position':[9335, -7106+(i%2)*110, 1015]}}
            result=controller.travel_stalled(state,world,i*3,['gate'])
        self.assertTrue(result)


if __name__=='__main__':unittest.main()
