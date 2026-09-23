import json,pathlib,tempfile,unittest
from dialogue_memory import DialogueMemory
from planner_mailbox import advice_for_world
from planner_destination import destination
from decision_context import focus_world_context,ScopeProgress,door_destination


class DialogueRecovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=pathlib.Path(self.temp.name)/'memory.json'
        self.state={'menus':[{'name':'dialogue','labels':[{'text':'Manny Vargas'}]}]}
        self.world={'crosshair':{'ref_id':'manny'},'cell_id':'room','quest':'They Went That-a-Way',
                    'objectives':[{'text':'Ask around Novac'}],'journal':[]}
        self.items=[{'text':'What was I supposed to do again?'},{'text':'Goodbye.'}]
        self.options={'0':self.items[0]['text'],'1':'Goodbye.','assist':'Ask Astra'}

    def test_repeated_speech_no_longer_counts_as_quest_progress(self):
        memory=DialogueMemory(self.path,1)
        for n in range(2):
            key,options,_=memory.filter(self.state,self.world,self.items,self.options,100+n)
            self.assertIn('0',options);memory.record(key,self.options['0'],100+n)
            self.state['menus'][0]['labels'].append({'text':'Repeated NPC speech '+str(n)})
        _,options,answered=memory.filter(self.state,self.world,self.items,self.options,103)
        self.assertNotIn('0',options);self.assertIn('1',options);self.assertIn('assist',options)
        self.assertEqual(answered,[self.options['0']])
        # A controller restart must not forget this observed loop.
        self.assertNotIn('0',DialogueMemory(self.path,1).filter(self.state,self.world,self.items,self.options,104)[1])

    def test_real_journal_progress_reopens_the_same_dialogue(self):
        memory=DialogueMemory(self.path,1)
        key,_,_=memory.filter(self.state,self.world,self.items,self.options,100)
        memory.record(key,self.options['0'],100);memory.record(key,self.options['0'],101)
        self.world['journal']=[{'quest':'They Went That-a-Way','text':'Intercept the Khans at Boulder City'}]
        self.assertIn('0',memory.filter(self.state,self.world,self.items,self.options,102)[1])

    def test_different_actor_expiration_and_undispatched_choices_are_allowed(self):
        memory=DialogueMemory(self.path,1)
        key,_,_=memory.filter(self.state,self.world,self.items,self.options,100)
        # Merely considering/discarding a decision must never count as input.
        self.assertIn('0',memory.filter(self.state,self.world,self.items,self.options,101)[1])
        memory.record(key,self.options['0'],102);memory.record(key,self.options['0'],103)
        self.world['crosshair']['ref_id']='another-actor'
        self.assertIn('0',memory.filter(self.state,self.world,self.items,self.options,104)[1])
        self.world['crosshair']['ref_id']='manny'
        self.assertIn('0',memory.filter(self.state,self.world,self.items,self.options,2000)[1])
        self.assertIn('0',DialogueMemory(self.path,2).filter(self.state,self.world,self.items,self.options,104)[1])


class DoorwayIntent(unittest.TestCase):
    def test_doors_show_the_observed_destination_instead_of_identical_names(self):
        self.assertEqual(door_destination({'destination':{'cell_name':'Great Khan Hideout'}}),'Great Khan Hideout')
        self.assertEqual(door_destination({'destination':{'cell_name':'','worldspace_id':'0xda726'}}),'Mojave Wasteland')
        self.assertEqual(door_destination({'destination':{'cell_name':'','worldspace_id':None}}),'another interior')
        self.assertIsNone(door_destination({'kind':28}))

    def test_exit_goal_becomes_handoff_outdoors_without_reentering(self):
        advice={'version':1,'stage':'room-stage','expires_at':200,'objective':'Leave the house','notes':[],
                'continuity':{'scopes':['room','wasteland'],'quest':'Trail','objective_contains':'Boulder'},
                'objectives_by_scope':{'wasteland':'You are outside. Select assist for fast travel.'}}
        state={'player':{'cell_id':'grid'}}
        world={'worldspace_id':'wasteland','quest':'Trail','objectives':[{'text':'Reach Boulder City'}]}
        self.assertEqual(advice_for_world(advice,'outside-stage',state,world,100)['objective'],
                         'You are outside. Select assist for fast travel.')
        self.assertIsNone(advice_for_world(advice,'outside-stage',state,world,201))

    def test_room_transition_preserves_intent_but_not_other_quests_or_rooms(self):
        advice={'version':1,'stage':'outside-stage','expires_at':200,'objective':'Read Manny terminal','notes':[],
                'continuity':{'scopes':['wasteland','manny-room'],'quest':'Trail','objective_contains':'Novac'}}
        state={'player':{'cell_id':'manny-room'}}
        world={'quest':'Trail','objectives':[{'text':'Ask around Novac'}]}
        self.assertIsNotNone(advice_for_world(advice,'inside-stage',state,world,100))
        state['player']['cell_id']='other-room'
        self.assertIsNone(advice_for_world(advice,'other-stage',state,world,100))
        state['player']['cell_id']='manny-room';world['objectives']=[{'text':'Reach Boulder City'}]
        self.assertIsNone(advice_for_world(advice,'new-stage',state,world,100))
        world['objectives']=[{'text':'Ask around Novac'}];world['quest']='Different quest'
        self.assertIsNone(advice_for_world(advice,'different-stage',state,world,100))
        world['quest']='Trail'
        self.assertIsNone(advice_for_world(advice,'inside-stage',state,world,201))

    def test_terminal_target_uses_its_own_interior_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'plan.json'
            path.write_text(json.dumps({'version':1,'expires_at':200,'objective_contains':'Novac','purpose':'Read terminal',
                'targets_by_scope':{'outside':{'ref_id':'door','name':'Room door','kind':28,'position':[10000,20000,7000]},
                                   'inside':{'ref_id':'terminal','name':'Terminal','kind':23,'position':[100,200,20]}}}))
            world={'cell_id':'inside','worldspace_id':None,'camera_position':[0,0,20],'camera_view':{'yaw':0},
                   'objectives':[{'text':'Ask around Novac'}]}
            target=destination(world,path,100)
            self.assertEqual(target['ref_id'],'terminal');self.assertLess(target['distance'],300)
            world['cell_id']='unrelated'
            self.assertIsNone(destination(world,path,100))


class FocusedDecisions(unittest.TestCase):
    def test_travel_keeps_goal_obstacles_recovery_and_combat(self):
        targets={'mission':{'quest_target':True,'distance':10000},'gate':{'distance':100},'stranger':{'distance':1000},'enemy':{'shootable':True,'distance':900}}
        options={'route:'+k:k for k in targets};options.update(left='Strafe',assist='Ask Astra')
        compact={'objective':'Finish game','objectives':['Reach Boulder City'],'player_combat':{'in_combat':False,'health_bar_fraction_approx':1},
                 'nearby':[{'id':k} for k in targets],'planner_advice':{'objective':'Follow the road'},'journal':[]}
        focused,available=focus_world_context(compact.copy(),options,targets)
        self.assertEqual(focused['immediate_goal'],'Follow the road')
        self.assertNotIn('route:stranger',available)
        self.assertTrue({'route:mission','route:gate','route:enemy','left','assist'}<=available.keys())
        compact['player_combat']['in_combat']=True
        self.assertEqual(focus_world_context(compact,options,targets)[1],options)

    def test_two_room_round_trips_trigger_but_new_progress_resets(self):
        guard=ScopeProgress();world={'objectives':[{'text':'Get the clue'}]}
        for i,cell in enumerate(['outside','room','outside','room','outside']):
            state={'player':{'cell_id':cell,'health_bar_fraction_approx':1,'equipped_weapon':'pistol'}}
            self.assertEqual(guard.observe(state,world,'same-plan',i*10),i==4)
        self.assertFalse(guard.observe(state,world,'new-terminal-plan',41))
        # Crossing different exterior grid cells is continuous travel.
        world['worldspace_id']='wasteland'
        for i in range(10):
            state['player']['cell_id']='grid-'+str(i%2)
            self.assertFalse(guard.observe(state,world,'travel',50+i))

if __name__=='__main__':unittest.main()
