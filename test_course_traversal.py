import unittest
from unittest.mock import Mock,patch
import course_traversal as c
import healing_hotkey as h

class CourseSafety(unittest.TestCase):
    def setUp(self):
        self.state={'player':{'position':[27000,123000,4900],'life_state':0,'health_bar_fraction_approx':.5},'interface_mode':1,'menus':[{'name':'hud'}]}
        self.world={'quest':'Wild Card: Side Bets','worldspace_id':'0xda726','disabled_controls':{'movement':False,'look':False}}
        self.target={'ref_id':'course-1','kind':0,'course_radius':155,'hazard':'nellis_artillery','prefer_direct':True}
    def test_general_travel_or_another_area_does_not_get_extended_control(self):
        self.assertTrue(c.allowed(self.state,self.world,self.target))
        self.assertFalse(c.allowed(self.state,dict(self.world,quest='Other quest'),self.target))
        self.assertFalse(c.allowed(self.state,self.world,dict(self.target,hazard=None)))
        self.assertFalse(c.allowed(dict(self.state,player=dict(self.state['player'],position=[0,0,0])),self.world,self.target))
    def test_death_combat_modal_and_disabled_controls_stop(self):
        for change in ({'life_state':2},{'in_combat':True}):
            self.assertFalse(c.allowed(dict(self.state,player=dict(self.state['player'],**change)),self.world,self.target))
        self.assertFalse(c.allowed(dict(self.state,menus=[{'name':'dialogue'}]),self.world,self.target))
        self.assertFalse(c.allowed(self.state,dict(self.world,disabled_controls={'movement':True,'look':False}),self.target))
    def test_last_stimpak_is_confirmed_only_after_actual_zero_inventory_read(self):
        obs=Mock();obs.snapshot.return_value=self.state
        item={'form_id':'0x15169','key':'8','count':1}
        with patch.object(h,'binding',side_effect=[item,None]),patch.object(h,'inventory_count',return_value=0),patch.object(h,'act') as act:
            result=h.use(obs,1,None,'test',move_forward=True)
        self.assertEqual(result['result']['count_after'],0)
        self.assertEqual(act.call_args.kwargs['keys'],['w','8'])
    def test_missing_binding_and_failed_inventory_read_never_claim_consumption(self):
        obs=Mock();obs.snapshot.return_value=self.state
        item={'form_id':'0x15169','key':'8','count':1}
        with patch.object(h,'binding',side_effect=[item,None]),patch.object(h,'inventory_count',return_value=None),patch.object(h,'act'),patch.object(h.time,'monotonic',side_effect=[0,2]):
            result=h.use(obs,1,None,'test')
        self.assertIn('handoff',result)
        self.assertNotIn('result',result)

if __name__=='__main__':unittest.main()
