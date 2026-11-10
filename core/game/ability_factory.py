"""AbilityFactory: creates Ability instances from an AbilityKind selector
or straight from a persisted AbilityData model (used by the Data layer
when loading a saved game)."""

from __future__ import annotations

from enum import Enum
from typing import Callable

from .abilities import Ability, Fireball, HealingLight, PowerStrike, TalentAbility
from .models import AbilityData


class AbilityKind(Enum):
    POWER_STRIKE = "power_strike"
    FIREBALL = "fireball"
    HEALING_LIGHT = "healing_light"
    TALENT = "talent"


class AbilityFactory:
    def __init__(self) -> None:
        self._builders: dict[AbilityKind, Callable[..., Ability]] = {
            AbilityKind.POWER_STRIKE: lambda **f: PowerStrike(bonus_damage=int(f.get("bonus_damage", 10))),
            AbilityKind.FIREBALL: lambda **f: Fireball(damage=int(f.get("damage", 25))),
            AbilityKind.HEALING_LIGHT: lambda **f: HealingLight(amount=int(f.get("amount", 15))),
            # New kind for imported talents: only a new enum member and a
            # new builder were needed - create()/from_data() are untouched.
            AbilityKind.TALENT: lambda **f: TalentAbility(
                f["name"], f.get("description", ""), f.get("talent_type", ""), float(f.get("multiplier", 1.0))
            ),
        }

    def create(self, kind: AbilityKind, **fields: str) -> Ability:
        builder = self._builders.get(kind)
        if builder is None:
            raise ValueError(f"Unknown ability kind: {kind}")
        return builder(**fields)

    def from_data(self, data: AbilityData) -> Ability:
        return self.create(AbilityKind(data.kind), **data.params)
