import json
from pathlib import Path
import tempfile
import time
import unittest
from decision_context import recent_menu_outcomes
from planner_mailbox import advice_for_world, restrict_dialogue_options


class MenuContinuity(unittest.TestCase):
    def test_dialogue_recovery_restricts_only_exact_speaker_and_keeps_assistance(self):
        plan={'version':1,'stage':'s','expires_at':200,'objective':'Recover chip',
              'dialogue_exclusions':{'Benny':['Scram.','Goodbye.']}}
        state={'player':{'cell_id':'suite'},'menus':[{'name':'dialogue','labels':[
            {'text':'Benny','path':'/DialogMenu/NOGLOW_BRANCH/DM_SpeakerNameLabel'}]}]}
        options={'0':'Scram.','2':'Attack','5':'Goodbye.','assist':'Ask Astra'}
        advice=advice_for_world(plan,'s',state,{},100)
        self.assertEqual(restrict_dialogue_options(state,advice,options)[0],{'2':'Attack','assist':'Ask Astra'})
        state['menus'][0]['labels'][0]['text']='Swank'
        self.assertEqual(restrict_dialogue_options(state,advice,options)[0],options)
        state['menus'][0]['labels'][0]['text']='Benny'
        self.assertEqual(restrict_dialogue_options(state,advice_for_world(plan,'s',state,{},201),options)[0],options)
        self.assertEqual(restrict_dialogue_options(state,advice_for_world(plan,'wrong',state,{},100),options)[0],options)

    def test_equipped_weapon_advances_goal_without_reopening_inventory(self):
        plan={'version':1,'stage':'s','expires_at':200,'objective':'Equip shotgun',
              'equipment_transition':{'scope':'casino','weapon':'Shotgun','then':'Use the elevator'}}
        state={'player':{'cell_id':'casino','equipped_weapon':'Shotgun'}}
        self.assertEqual(advice_for_world(plan,'s',state,{},100)['objective'],'Use the elevator')
        state['player']['equipped_weapon']='Rifle'
        self.assertEqual(advice_for_world(plan,'s',state,{},100)['objective'],'Equip shotgun')

    def test_purchase_and_goodbye_reach_world_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'history.json'
            rows=[{'selected':'<Pay 500 caps> Okay, I will take one.','result':'Menu changed'},
                  {'selected':'Goodbye.','result':'Menu changed'}]
            path.write_text(json.dumps({'pid':1,'updated_at':90,'results':rows}))
            self.assertEqual(recent_menu_outcomes(path,1,100),rows)
            self.assertEqual(recent_menu_outcomes(path,2,100),[])
            self.assertEqual(recent_menu_outcomes(path,1,700),[])
            path.write_text(json.dumps({'pid':1,'updated_at':time.time(),'results':rows}))
            self.assertEqual(recent_menu_outcomes(path,1),rows)


if __name__=='__main__':unittest.main()
