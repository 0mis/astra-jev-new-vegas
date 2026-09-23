"""Detect continuing noncombat injury from observed HUD samples, not guesses."""
from collections import deque
import math


def nellis_artillery_traversal(world,player,targets):
    position=player.get('position') or []
    return bool(world.get('quest')=='Wild Card: Side Bets' and world.get('worldspace_id')=='0xda726'
                and len(position)==3 and 25000<=position[0]<=35000 and 120500<=position[1]<=131000
                and any(t.get('kind')==0 and t.get('course_radius') and t.get('hazard')=='nellis_artillery'
                        for t in targets.values()))


class DamageWatch:
    def __init__(self):
        self.samples = deque(maxlen=12)

    def observe(self, player, now):
        hp = player.get('health_bar_fraction_approx')
        if (player.get('life_state') != 0 or player.get('in_combat')
                or not isinstance(hp, (int, float)) or not math.isfinite(hp)
                or not 0 <= hp <= 1):
            self.samples.clear()
            return None
        while self.samples and now - self.samples[0][0] > 30:
            self.samples.popleft()
        if self.samples and hp > self.samples[-1][1] + .02:
            self.samples.clear()
        if self.samples and now <= self.samples[-1][0]:
            return None
        self.samples.append((now, hp))
        if len(self.samples) < 2 or hp >= .8:
            return None
        first = self.samples[0]
        loss = first[1] - hp
        declines = sum(b[1] < a[1] - .009 for a, b in zip(self.samples, list(self.samples)[1:]))
        if now - first[0] >= 1 and (loss >= .08 or (declines >= 2 and loss >= .04)):
            return {'reason': 'Health continues falling outside combat; inspect active effects before travel.',
                    'health_before': first[1], 'health_now': hp,
                    'elapsed_seconds': round(now - first[0], 2)}
        return None
