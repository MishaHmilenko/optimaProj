"""Generates combat stats for imported characters.

The genshin.dev database has no base stats, so - as the practical
allows - they are rolled randomly from a range that depends on rarity.
The random source is injected, which keeps the generator deterministic
in tests (random.Random(seed)) and random in the real application.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Stats:
    health: int
    armor: int
    attack_power: int


class StatGenerator:
    # rarity -> (minimum stats, maximum stats), both inclusive
    RANGES: dict[int, tuple[Stats, Stats]] = {
        3: (Stats(70, 3, 8), Stats(95, 7, 12)),
        4: (Stats(90, 5, 12), Stats(115, 10, 17)),
        5: (Stats(110, 8, 16), Stats(140, 14, 22)),
    }

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()

    def generate(self, rarity: int) -> Stats:
        clamped = min(max(rarity, min(self.RANGES)), max(self.RANGES))
        low, high = self.RANGES[clamped]
        return Stats(
            health=self._rng.randint(low.health, high.health),
            armor=self._rng.randint(low.armor, high.armor),
            attack_power=self._rng.randint(low.attack_power, high.attack_power),
        )
