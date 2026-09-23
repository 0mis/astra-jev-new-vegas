import math
from pathlib import Path
import tempfile
import unittest
from loop_watchdog import ProgressWatch, publish_alert
from decision_context import scripted_observation


class WatchdogTests(unittest.TestCase):
    def test_verified_demo_is_not_travel_but_still_has_deadline(self):
        w=ProgressWatch()
        changes={'quest':'Wild Card: Change in Management','scope':'0x1221c4',
                 'objectives':['Observe upgrading of Securitrons.']}
        for t in range(0,301,3):
            self.assertIsNone(self.feed(w,t,[5966,-2520,8599],**changes))
        self.assertEqual(self.feed(w,303,[5966,-2520,8599],**changes)['reason'],'scripted_scene_stalled')

    def test_observation_exemption_requires_exact_scene_and_does_not_persist(self):
        self.assertFalse(scripted_observation('Wild Card: Side Bets','0x1221c4',['Observe the Omertas at their casino, Gomorrah.']))
        self.assertFalse(scripted_observation('Wild Card: Change in Management','outside',['Observe upgrading of Securitrons.']))
        w=ProgressWatch()
        for t in range(0,61,3):
            self.feed(w,t,[0,0,0],quest='Wild Card: Change in Management',scope='0x1221c4',objectives=['Observe upgrading of Securitrons.'])
        result=None
        for t in range(63,109,3):result=self.feed(w,t,[0,0,0],progress='next-quest')
        self.assertEqual(result['reason'],'local_movement_loop')

    def feed(self, watch, t, position, **changes):
        sample = dict(at=t, pid=1, progress='quest-plan', scope='world', position=position,
                      menus=['hud'], combat=False, target_id='gate', target_distance=200)
        sample.update(changes)
        status = dict(state='running', pid=1, started_at=0, updated_at=t,
                      decisions=int(t/3), last_choice='forward')
        return watch.observe(status, sample, t)

    def test_real_near_gate_oscillation_is_caught(self):
        w = ProgressWatch()
        for t in range(0, 46, 3):
            result = self.feed(w, t, [9335, -7106+(t//3%2)*110, 1015])
        self.assertEqual(result['reason'], 'local_movement_loop')

    def test_sustained_travel_and_vertical_progress_continue(self):
        for axis in (0, 2):
            w = ProgressWatch()
            for t in range(0, 181, 3):
                pos = [0, 0, 0]; pos[axis] = t*50
                self.assertIsNone(self.feed(w, t, pos))

    def test_combat_and_long_barter_are_not_travel_loops(self):
        for changes in ({'combat':True}, {'menus':['hud','barter']}, {'movement_available':False}):
            w = ProgressWatch()
            for t in range(0, 121, 3):
                self.assertIsNone(self.feed(w, t, [0, 0, 0], **changes))

    def test_new_plan_resets_progress_window(self):
        w = ProgressWatch()
        for t in range(0, 61, 3):
            self.assertIsNone(self.feed(w, t, [0, 0, 0], progress=str(t//30)))

    def test_large_circle_is_caught(self):
        w = ProgressWatch(); result = None
        for t in range(0, 73, 3):
            result = self.feed(w, t, [800*math.cos(t*math.tau/72),800*math.sin(t*math.tau/72),0], target_distance=3000)
            if result: break
        self.assertEqual(result['reason'], 'returning_travel_loop')

    def test_room_cycle_caught_across_scope_changes(self):
        w = ProgressWatch()
        for i, scope in enumerate('ababa'):
            result = self.feed(w, i*15, [0, 0, 0], scope=scope)
        self.assertEqual(result['reason'], 'room_cycle')

    def test_circle_cannot_reset_progress_by_approaching_same_point_each_lap(self):
        w = ProgressWatch(); result = None
        for t in range(0, 151, 3):
            pos = [800*math.cos(t*math.tau/72),800*math.sin(t*math.tau/72),0]
            remaining = math.dist(pos,[4000,0,0])
            result = self.feed(w,t,pos,target_distance=remaining)
            if result: break
        self.assertEqual(result['reason'], 'returning_travel_loop')

    def test_dialogue_cycles_only_on_new_decisions(self):
        w = ProgressWatch()
        for t in range(0, 31, 3):
            result = self.feed(w, t, [0, 0, 0], menus=['dialogue'], dialogue_key='same-answers')
        self.assertEqual(result['reason'], 'dialogue_cycle')
        w = ProgressWatch()
        for t in range(0, 91, 3):
            status = dict(state='running',pid=1,started_at=0,updated_at=t,decisions=1,last_choice='hello')
            sample = dict(pid=1,at=t,progress='same',scope='a',menus=['dialogue'],dialogue_key='same-answers')
            self.assertIsNone(w.observe(status, sample, t))

    def test_inactive_and_stale_observations_do_not_stop_manual_work(self):
        w = ProgressWatch()
        self.assertIsNone(w.observe({'state':'needs_planner'}, {}, 100))
        status = dict(state='running',pid=1,started_at=1,updated_at=100)
        self.assertIsNone(w.observe(status, {'pid':2,'at':100}, 100))
        self.assertIsNone(w.observe(status, {'pid':1,'at':10}, 100))
        status['updated_at'] = 50
        self.assertEqual(w.observe(status, {}, 100)['reason'], 'controller_unresponsive')

    def test_terminal_open_back_cycle_is_caught_without_travel(self):
        watch = ProgressWatch()
        for t in range(0, 46, 3):
            status = dict(state='running', pid=1, started_at=0, updated_at=t,
                          decisions=t//3, last_choice='Open Antechamber' if t%6 == 0 else 'Back')
            sample = dict(pid=1, at=t, progress='door-already-open', scope='penthouse',
                          menus=['hud', 'computer'], terminal_key='root' if t%6 == 0 else 'result')
            result = watch.observe(status, sample, t)
            if result: break
        self.assertEqual(result['reason'], 'terminal_cycle')

    def test_terminal_waiting_and_distinct_pages_are_not_cycles(self):
        for mode in ('waiting', 'new-pages'):
            watch = ProgressWatch()
            for t in range(0, 121, 3):
                status = dict(state='running', pid=1, started_at=0, updated_at=t,
                              decisions=1 if mode == 'waiting' else t//3, last_choice='Read')
                sample = dict(pid=1, at=t, progress='same', scope='penthouse',
                              menus=['computer'], terminal_key='same' if mode == 'waiting' else str(t))
                self.assertIsNone(watch.observe(status, sample, t))

    def test_actual_unlock_progress_resets_terminal_cycle_window(self):
        watch = ProgressWatch()
        for t in range(0, 91, 3):
            status = dict(state='running', pid=1, started_at=0, updated_at=t,
                          decisions=t//3, last_choice='Open')
            sample = dict(pid=1, at=t, progress='locks-'+str(t//20), scope='penthouse',
                          menus=['computer'], terminal_key='access')
            self.assertIsNone(watch.observe(status, sample, t))

    def test_alert_deduplicates_and_preserves_prior_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); stop = root/'controller.stop'; stop.write_text('other safety reason')
            status = dict(pid=1,started_at=42)
            why = dict(reason='loop',detail='Repeated path')
            a = publish_alert(root,status,{},why,100)
            self.assertEqual(a,publish_alert(root,status,{},why,103))
            self.assertEqual(stop.read_text(),'other safety reason')
            self.assertEqual(len((root/'loop-watchdog-events.jsonl').read_text().splitlines()),1)

    def test_equipment_close_loop_caught_even_when_every_sample_is_in_menu(self):
        w=ProgressWatch()
        for t in range(0,31,3):
            status=dict(state='running',pid=1,started_at=0,updated_at=t,
                        decisions=t,last_choice='equipment:close')
            sample=dict(pid=1,at=t,progress='shotgun-equipped-hp-full',scope='casino',
                        menus=['inventory','hud'],position=[0,0,0])
            result=w.observe(status,sample,t)
            if result:break
        self.assertEqual(result['reason'],'menu_open_close_loop')

    def test_loadout_changes_and_actual_travel_reset_menu_cycle_evidence(self):
        for changing in ('loadout','travel'):
            w=ProgressWatch()
            for t in range(0,91,3):
                status=dict(state='running',pid=1,started_at=0,updated_at=t,
                            decisions=t,last_choice='equipment:close')
                sample=dict(pid=1,at=t,progress=str(t//15) if changing=='loadout' else 'same',
                            scope='casino',menus=['inventory','hud'],
                            position=[t*50 if changing=='travel' else 0,0,0])
                self.assertIsNone(w.observe(status,sample,t))


if __name__ == '__main__': unittest.main()
