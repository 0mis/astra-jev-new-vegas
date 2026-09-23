"""Independent read-only progress checks; asks the sole input owner to stop.

Never sends game input, restarts a plan, calls a model, or publishes anything.
The same-thread heartbeat brings evidence to Astra for an actual recovery.
"""
import argparse
from collections import Counter, deque
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from decision_context import scripted_observation

ROOT = Path(__file__).resolve().parent


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {} if default is None else default


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:20]


class ProgressWatch:
    def __init__(self):
        self.run = self.progress = self.travel_key = None
        self.travel = deque()
        self.scopes = deque(maxlen=5)
        self.dialogue = deque()
        self.last_decisions = None
        self.best_target_distance = None
        self.last_target_improvement = None
        self.menu_actions = deque()
        self.last_activity_decisions = None
        self.script_since = None

    def observe(self, status, sample, now):
        run = (status.get('pid'), status.get('started_at'))
        if status.get('state') != 'running':
            self.__init__()
            return None
        if run != self.run:
            self.__init__()
            self.run = run
        if now - status.get('updated_at', status.get('started_at', now)) > 45:
            return {'reason': 'controller_unresponsive', 'detail': 'No controller heartbeat for over 45 seconds'}
        if sample.get('pid') != status.get('pid') or now - sample.get('at', 0) > 6:
            return None
        progress = sample['progress']
        if progress != self.progress:
            self.progress = progress
            self.scopes.clear()
            self.travel.clear()
            self.dialogue.clear()
            self.menu_actions.clear()
        scope = sample.get('scope')
        if scope and (not self.scopes or self.scopes[-1][1] != scope):
            self.scopes.append((now, scope))
        if len(self.scopes) == 5 and now - self.scopes[0][0] <= 120:
            a, b, c, d, e = [s for _, s in self.scopes]
            if a == c == e and b == d and a != b:
                return {'reason': 'room_cycle', 'detail': 'Repeated A-B-A-B-A room visits without quest or plan progress'}
        menus = set(sample.get('menus', [])) - {'hud', 'tutorial'}
        # Travel windows intentionally exclude menus, so they cannot detect
        # repeated open/close cycles. Check completed menu actions separately,
        # including when a three-second sample misses the brief HUD interval.
        if sample.get('combat'):
            self.menu_actions.clear()
        elif status.get('decisions') != self.last_activity_decisions:
            self.last_activity_decisions = status.get('decisions')
            choice = status.get('last_choice')
            if choice in ('equipment', 'equipment:close', 'pipboy', 'health') and sample.get('position'):
                self.menu_actions.append((now, choice, sample['position']))
            while self.menu_actions and now-self.menu_actions[0][0] > 75:
                self.menu_actions.popleft()
            if len(self.menu_actions) >= 4 and now-self.menu_actions[0][0] >= 20:
                counts = Counter(row[1] for row in self.menu_actions)
                origin = self.menu_actions[0][2]
                span = max(math.dist(origin,row[2]) for row in self.menu_actions)
                if max(counts.values()) >= 4 and span < 250:
                    return {'reason':'menu_open_close_loop',
                            'detail':'Repeated inventory/status opens or closes without equipment, health, quest or travel progress'}
        # Menus and combat are not travel. Long conversations are fine unless
        # the SAME dispatched choice and ready answers keep coming back.
        if menus or sample.get('combat') or not sample.get('movement_available', True):
            self.travel.clear()
            ready_menu = 'computer' if 'computer' in menus else 'dialogue'
            ready_key = sample.get('terminal_key') if ready_menu == 'computer' else sample.get('dialogue_key')
            if ready_menu in menus and ready_key:
                count = status.get('decisions')
                if count != self.last_decisions:
                    self.dialogue.append((now, (ready_menu, ready_key), status.get('last_choice')))
                    self.last_decisions = count
                while self.dialogue and now - self.dialogue[0][0] > 90:
                    self.dialogue.popleft()
                repeats = Counter((key, choice) for _, key, choice in self.dialogue)
                if self.dialogue and now - self.dialogue[0][0] >= 25 and max(repeats.values(), default=0) >= 3:
                    return {'reason': 'terminal_cycle' if ready_menu == 'computer' else 'dialogue_cycle',
                            'detail': 'Same choice returned at least three times with unchanged ready controls and no observed progress'}
            return None
        if scripted_observation(sample.get('quest'),scope,sample.get('objectives',[])):
            self.travel.clear()
            if self.script_since is None:self.script_since=now
            if now-self.script_since>300:
                return {'reason':'scripted_scene_stalled','detail':'Verified basement demonstration has not advanced for five minutes'}
            return None
        self.script_since=None
        key = (scope, sample.get('target_id'))
        if key != self.travel_key:
            self.travel.clear()
            self.travel_key = key
            self.best_target_distance = None
            self.last_target_improvement = now
        pos = sample.get('position')
        if not pos or not all(math.isfinite(v) for v in pos):
            return None
        self.travel.append((now, pos, sample.get('target_distance')))
        remaining = sample.get('target_distance')
        if remaining is not None and (self.best_target_distance is None or remaining < self.best_target_distance-100):
            self.best_target_distance = remaining
            self.last_target_improvement = now
        while self.travel and now - self.travel[0][0] > 93:
            self.travel.popleft()
        if len(self.travel) < 5:
            return None
        recent = [row for row in self.travel if now - row[0] <= 45]
        if recent and now - recent[0][0] >= 40:
            xs, ys, zs = zip(*(row[1] for row in recent))
            span = math.hypot(max(xs)-min(xs), max(ys)-min(ys))
            if span < 350 and max(zs)-min(zs) < 160:
                return {'reason': 'local_movement_loop', 'detail': 'Over 40 seconds in the same small area',
                        'span': round(span, 1), 'seconds': round(now-recent[0][0], 1)}
        # A larger loop can travel far each step, yet return to the same place.
        older = [row for row in self.travel if now-row[0] >= 60]
        for anchor in older:
            if math.dist(anchor[1], pos) > 180:
                continue
            segment = [row for row in self.travel if row[0] >= anchor[0]]
            distance = sum(math.dist(a[1], b[1]) for a, b in zip(segment, segment[1:]))
            # A circular path may briefly get closer on EVERY lap. Compare
            # against the best distance across laps, not each window's start.
            improving = remaining is not None and now-self.last_target_improvement < 45
            if distance >= 700 and not improving:
                return {'reason': 'returning_travel_loop', 'detail': 'Travel returned to the same place without approaching the target',
                        'path_distance': round(distance, 1), 'seconds': round(now-anchor[0], 1)}
        return None


def observe_game(observer, status, now):
    from planner_destination import destination
    state = observer.snapshot(include_labels=False)
    menus = [m['name'] for m in state['menus']]
    if 'dialogue' in menus or 'computer' in menus:
        state = observer.snapshot()
    world = observer.world(state, nearby_ref_ids=())
    player = state.get('player') or {}
    advice = read_json(ROOT/'planner-advice.json')
    plan = read_json(ROOT/'planner-destination.json')
    target = destination(world, now=now)
    objectives = [o['text'] for o in world.get('objectives', [])]
    # Health and ammo fluctuate during combat; those are not plan revisions.
    journal = [(o.get('quest'), o.get('text'), o.get('active')) for o in world.get('journal', [])]
    hp = player.get('health_bar_fraction_approx')
    door_locks = sorted((r['ref_id'], r.get('locked')) for r in world.get('doors', [])
                        if r.get('same_space') and r.get('locked') is not None)
    progress = signature([world.get('quest'), objectives, journal, advice.get('revision'), door_locks,
                          player.get('equipped_weapon'),round(hp,1) if hp is not None else None,
                          plan.get('purpose'), plan.get('target'), plan.get('targets_by_scope')])
    dialogue = next((m for m in state['menus'] if m['name'] == 'dialogue'), None)
    ready = sorted(x['text'] for x in (dialogue or {}).get('labels', [])
                   if x.get('target') and '/DM_TopicList/' in x['path'])
    terminal = next((m for m in state['menus'] if m['name'] == 'computer'), None)
    terminal_ready = sorted(x['text'] for x in (terminal or {}).get('labels', [])
                            if x.get('target') and '/computers_file_directory/' in x['path'])
    return {'at': now, 'pid': state['pid'], 'position': player.get('position'),
            'scope': world.get('worldspace_id') or player.get('cell_id'),
            'menus': menus, 'combat': player.get('in_combat'), 'progress': progress,
            'quest': world.get('quest'), 'objectives': objectives,
            'movement_available': not world.get('disabled_controls', {}).get('movement'),
            'target_id': (target or {}).get('ref_id'), 'target_distance': (target or {}).get('distance'),
            'dialogue_key': signature([(world.get('crosshair') or {}).get('ref_id'), ready]) if ready else None,
            'terminal_key': signature([(world.get('crosshair') or {}).get('ref_id'), terminal_ready]) if terminal_ready else None}


def publish_alert(root, status, sample, reason, now):
    from planner_mailbox import atomic_json
    key = signature([status.get('pid'), status.get('started_at')])
    old = read_json(root/'planner-loop-alert.json')
    if old.get('run_key') == key:
        return old
    alert = {'version': 1, 'at': now, 'run_key': key, 'controller_started_at': status.get('started_at'),
             'pid': status.get('pid'), **reason, 'sample': sample,
             'recovery': 'Astra must inspect and change the failing plan before resuming.'}
    atomic_json(root/'planner-loop-alert.json', alert)
    # Exclusive create preserves another stop request and its reason.
    try:
        with (root/'controller.stop').open('x', encoding='utf-8') as f:
            f.write('Independent loop watchdog: '+reason['detail'])
    except FileExistsError:
        pass
    with (root/'loop-watchdog-events.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(alert)+'\n')
    return alert


def main():
    import msvcrt
    from observe_game import Observer
    from decide_game import recording_health
    from planner_mailbox import atomic_json
    lock = (ROOT/'loop-watchdog.lock').open('a+b')
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'0'); lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock.close()
        return
    watch = ProgressWatch()
    observer = None
    errors = capture_errors = 0
    try:
        while not (ROOT/'loop-watchdog.stop').exists():
            now = time.time()
            status = read_json(ROOT/'loop-status.json')
            report = {'at': now, 'worker_pid': os.getpid(), 'interval_seconds': 3,
                      'state': 'monitoring' if status.get('state') == 'running' else 'awaiting_controller',
                      'controller_state': status.get('state'), 'game_pid': status.get('pid')}
            try:
                pid = status.get('pid')
                if pid and (observer is None or observer.pid != pid):
                    if observer: observer.close()
                    observer = Observer(pid)
                sample = observe_game(observer, status, now) if observer else {}
                report['sample'] = sample
                errors = 0
                reason = watch.observe(status, sample, now)
                try:
                    report['recording'] = recording_health(ROOT/status['recording'])
                    capture_errors = 0
                except Exception as exc:
                    capture_errors += 1
                    report['recording_error'] = str(exc)
                    if capture_errors >= 2 and status.get('state') == 'running':
                        reason = {'reason': 'recording_unhealthy', 'detail': str(exc)}
                if reason:
                    report['alert'] = publish_alert(ROOT, status, sample, reason, now)
                    report['state'] = 'handoff_requested'
            except Exception as exc:
                errors += 1
                report.update(state='observation_error', error=str(exc), consecutive_errors=errors)
                if status.get('state') == 'running' and errors >= 5:
                    report['alert'] = publish_alert(ROOT, status, {},
                        {'reason': 'watchdog_blind', 'detail': 'Independent observation failed five times; inspect before continuing'}, now)
            atomic_json(ROOT/'loop-watchdog-status.json', report, best_effort=True)
            time.sleep(3)
    finally:
        if observer: observer.close()
        atomic_json(ROOT/'loop-watchdog-status.json', {'at':time.time(), 'state':'stopped', 'worker_pid':os.getpid()})
        lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1); lock.close()


def ensure():
    if (ROOT/'loop-watchdog.stop').exists():
        raise RuntimeError('Watchdog deliberately stopped; inspect before restarting it')
    latest = read_json(ROOT/'loop-watchdog-status.json')
    usable = {'monitoring', 'awaiting_controller', 'handoff_requested'}
    if time.time()-latest.get('at', 0) < 8 and latest.get('state') in usable:
        return
    with (ROOT/'loop-watchdog.log').open('ab') as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve())], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic()+8
    while time.monotonic() < deadline:
        latest = read_json(ROOT/'loop-watchdog-status.json')
        if time.time()-latest.get('at', 0) < 4 and latest.get('state') in usable:
            return
        time.sleep(.25)
    raise RuntimeError('Independent watchdog did not produce a fresh heartbeat')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ensure', action='store_true')
    args = parser.parse_args()
    ensure() if args.ensure else main()
