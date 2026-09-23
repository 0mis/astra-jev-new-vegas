import unittest
from world_controller import WorldController

class DeathHandoff(unittest.TestCase):
    def test_dying_and_dead_stop_even_during_death_camera(self):
        controller=WorldController.__new__(WorldController)
        for life in (1,2):
            result=controller._step(None,None,17776,None,{'player':{'life_state':life},'vats_mode':4})
            self.assertTrue(result['death_observed'])
            self.assertFalse(result['input_sent'])
            self.assertIn('change the failed plan',result['handoff'])

if __name__=='__main__':unittest.main()
