import unittest
from unittest.mock import Mock,patch
import healing_hotkey as h

class HealingGuards(unittest.TestCase):
    def setUp(self):
        self.state={'player':{'health_bar_fraction_approx':.3,'life_state':0},'interface_mode':1,'menus':[{'name':'hud'}]}
        self.item={'form_id':'0x15169','key':'8','count':6}
    def test_wrong_item_cannot_be_used_as_healing(self):
        self.assertFalse(h.available(self.state,dict(self.item,form_id='0x1613d0')))
    def test_empty_inventory_and_ammo_switch_key_are_rejected(self):
        self.assertFalse(h.available(self.state,dict(self.item,count=0)))
        self.assertFalse(h.available(self.state,dict(self.item,key='2')))
    def test_full_health_and_open_menus_do_not_offer_healing(self):
        self.assertTrue(h.available(self.state,self.item))
        self.assertFalse(h.available(dict(self.state,player={'health_bar_fraction_approx':1,'life_state':0}),self.item))
        self.assertFalse(h.available(dict(self.state,menus=[{'name':'barter'}]),self.item))
    def test_lost_binding_after_decision_sends_no_input(self):
        observer=Mock();observer.snapshot.return_value=self.state
        with patch.object(h,'binding',return_value=None),patch.object(h,'act') as act:
            self.assertIn('discarded',h.use(observer,1,None,'test'))
            act.assert_not_called()

if __name__=='__main__':unittest.main()
