import unittest
from damage_watch import DamageWatch


def player(hp, combat=False):
    return {'health_bar_fraction_approx': hp, 'in_combat': combat, 'life_state': 0}


class PoisonRegression(unittest.TestCase):
    def test_long_conversation_does_not_count_as_stalled_walking(self):
        from collections import deque
        from world_controller import WorldController
        controller=WorldController.__new__(WorldController);controller.travel_samples=deque()
        state={'player':{'cell_id':'Boulder','position':[0,0,0]}}
        world={'objectives':[{'text':'Meet Jessup'}]}
        self.assertFalse(controller.travel_stalled(state,world,0,['entrance']))
        controller.exclude_menu_time()
        # A 90-second conversation at the same entrance must not trigger.
        self.assertFalse(controller.travel_stalled(state,world,90,['entrance']))
        for now in range(94,130,4):
            self.assertFalse(controller.travel_stalled(state,world,now,['entrance']))
        # Forty subsequent seconds of actual failed travel still do trigger.
        self.assertTrue(controller.travel_stalled(state,world,130,['entrance']))

    def test_terrain_recovery_is_not_suggested_after_merely_turning(self):
        from gameplay_skills import relevant_lessons
        world={'disabled_controls':{'movement':False},'objectives':[],'nearby':[]}
        turn={'action':'Use a floor route','movement_attempted':False,'moved_units':0,'target_distance_after':1000}
        self.assertNotIn('terrain_lip_recovery',[x['skill'] for x in relevant_lessons(world,[turn])])
        turn['movement_attempted']=True
        self.assertIn('terrain_lip_recovery',[x['skill'] for x in relevant_lessons(world,[turn])])
        turn['target_distance_after']=20
        self.assertNotIn('terrain_lip_recovery',[x['skill'] for x in relevant_lessons(world,[turn])])

    def test_observed_post_combat_drain_stops_well_before_critical_hp(self):
        guard = DamageWatch()
        self.assertIsNone(guard.observe(player(.493), 0))
        self.assertIsNone(guard.observe(player(.467), 3))
        evidence = guard.observe(player(.44), 6)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence['health_now'], .44)

    def test_combat_and_stable_low_health_do_not_block_recovery_travel(self):
        guard = DamageWatch()
        self.assertIsNone(guard.observe(player(.9, True), 0))
        self.assertIsNone(guard.observe(player(.4, True), 3))
        for t in range(4, 50):
            self.assertIsNone(guard.observe(player(.04), t))

    def test_healing_old_samples_and_hud_noise_do_not_trigger(self):
        guard = DamageWatch()
        for t, hp in [(0, .5), (3, .493), (4, .5), (5, .493), (6, 1), (40, .9), (41, .893)]:
            self.assertIsNone(guard.observe(player(hp), t))
        self.assertIsNone(guard.observe(player(float('nan')), 42))


if __name__ == '__main__':
    unittest.main()
