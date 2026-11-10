"""Abilities: compute an effect and return a description (AbilityResult)
instead of printing. Each concrete ability also knows how to describe
itself as a pure AbilityData model, for persistence.

TEMPLATE METHOD: Ability.use() is the fixed algorithm shared by every
ability -

    1. check the target (if this ability needs one)
    2. pick who is affected (the target, or the user for self-casts)
    3. apply the effect                     -> _apply()     (varies)
    4. describe what happened               -> _describe()  (varies)

Subclasses can't reorder or skip steps; they only fill in the two
varying ones (plus the requires_target flag). Before this refactor each
ability repeated the target check and result wrapping in its own use().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import AbilityData

if TYPE_CHECKING:
    from .character import Character


@dataclass(frozen=True)
class AbilityResult:
    message: str


class Ability(ABC):
    name: str = "Ability"
    requires_target: bool = True

    def use(self, user: "Character", target: "Character | None" = None) -> AbilityResult:
        """The template method - not meant to be overridden."""
        if self.requires_target and target is None:
            raise ValueError(f"{self.name} requires a target")
        recipient = target or user
        amount = self._apply(user, recipient)
        return AbilityResult(self._describe(user, recipient, amount))

    @abstractmethod
    def _apply(self, user: "Character", recipient: "Character") -> int:
        """Perform the effect; return the amount of damage/healing done."""
        raise NotImplementedError

    def _describe(self, user: "Character", recipient: "Character", amount: int) -> str:
        """Default wording for damaging abilities; others override it."""
        return f"{user.name} uses {self.name} on {recipient.name} for {amount} damage!"

    @abstractmethod
    def to_data(self) -> AbilityData:
        """Describe this ability as a plain, serializable model."""
        raise NotImplementedError


class PowerStrike(Ability):
    name = "Power Strike"

    def __init__(self, bonus_damage: int = 10) -> None:
        self.bonus_damage = bonus_damage

    def _apply(self, user: "Character", recipient: "Character") -> int:
        raw_damage = user.attack_power + self.bonus_damage
        return recipient.take_damage(raw_damage, armor_penetration=0.5)

    def to_data(self) -> AbilityData:
        return AbilityData(kind="power_strike", name=self.name, params={"bonus_damage": str(self.bonus_damage)})


class HealingLight(Ability):
    name = "Healing Light"
    requires_target = False  # heals the user when cast without a target

    def __init__(self, amount: int = 15) -> None:
        self.amount = amount

    def _apply(self, user: "Character", recipient: "Character") -> int:
        return recipient.heal(self.amount)

    def _describe(self, user: "Character", recipient: "Character", amount: int) -> str:
        return f"{user.name} casts {self.name} on {recipient.name}, healing {amount} HP."

    def to_data(self) -> AbilityData:
        return AbilityData(kind="healing_light", name=self.name, params={"amount": str(self.amount)})


class TalentAbility(Ability):
    """A named talent imported from the character database.

    The remote data only describes talents in prose, so the combat
    effect is derived from the talent type: damage is the user's attack
    power times a multiplier (normal attack < skill < burst)."""

    MULTIPLIERS = {
        "NORMAL_ATTACK": 1.0,
        "ELEMENTAL_SKILL": 1.5,
        "ELEMENTAL_BURST": 2.5,
    }

    def __init__(self, name: str, description: str, talent_type: str, multiplier: float) -> None:
        self.name = name
        self.description = description
        self.talent_type = talent_type
        self.multiplier = multiplier

    @classmethod
    def for_type(cls, name: str, description: str, talent_type: str) -> "TalentAbility":
        return cls(name, description, talent_type, cls.MULTIPLIERS.get(talent_type, 1.0))

    def _apply(self, user: "Character", recipient: "Character") -> int:
        return recipient.take_damage(round(user.attack_power * self.multiplier))

    def to_data(self) -> AbilityData:
        return AbilityData(
            kind="talent",
            name=self.name,
            params={
                "name": self.name,
                "description": self.description,
                "talent_type": self.talent_type,
                "multiplier": str(self.multiplier),
            },
        )


class Fireball(Ability):
    name = "Fireball"

    def __init__(self, damage: int = 25) -> None:
        self.damage = damage

    def _apply(self, user: "Character", recipient: "Character") -> int:
        return recipient.take_damage(self.damage, ignore_armor=True)

    def _describe(self, user: "Character", recipient: "Character", amount: int) -> str:
        return f"{user.name} hurls a {self.name} at {recipient.name} for {amount} damage!"

    def to_data(self) -> AbilityData:
        return AbilityData(kind="fireball", name=self.name, params={"damage": str(self.damage)})
