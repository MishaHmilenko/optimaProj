"""Character wraps CharacterData; all behaviour (combat, equipping,
learning abilities) lives here, state lives in the model."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from infra.rendering import IRenderable, IRenderer

from .models import CharacterData

if TYPE_CHECKING:
    from .abilities import Ability
    from .items import Item


class CharacterMemento:
    """MEMENTO: an opaque snapshot of a Character's state.

    It has no public attributes or methods - nothing outside Character
    can read or change what it holds. Only Character (the originator)
    creates it in save_state() and reads it back in restore_state().
    Whoever stores mementos (a command, an undo history) just keeps them.
    """

    __slots__ = ("_data", "_abilities", "_equipment", "_defending")

    def __init__(self, data: CharacterData, abilities: dict, equipment: list, defending: bool) -> None:
        self._data = data
        self._abilities = abilities
        self._equipment = equipment
        self._defending = defending


class Character(IRenderable):
    def __init__(self, data: CharacterData) -> None:
        self.data = data
        self._abilities: dict[str, "Ability"] = {}
        self._equipment: list["Item"] = []
        self._defending = False

    @property
    def name(self) -> str:
        return self.data.name

    @property
    def health(self) -> int:
        return self.data.health

    @property
    def max_health(self) -> int:
        return self.data.max_health

    @property
    def armor(self) -> int:
        return self.data.armor

    @property
    def attack_power(self) -> int:
        return self.data.attack_power

    @property
    def is_alive(self) -> bool:
        return self.data.health > 0

    @property
    def abilities(self) -> tuple[str, ...]:
        return tuple(self._abilities)

    @property
    def abilities_map(self) -> dict[str, "Ability"]:
        return dict(self._abilities)

    @property
    def equipment(self) -> tuple["Item", ...]:
        return tuple(self._equipment)

    def take_damage(self, amount: int, ignore_armor: bool = False,
                     armor_penetration: float = 0.0) -> int:
        effective_armor = 0 if ignore_armor else round(self.data.armor * (1 - armor_penetration))
        damage = max(amount - effective_armor, 0)
        if self._defending:
            damage //= 2
        self.data.health = max(self.data.health - damage, 0)
        return damage

    def heal(self, amount: int) -> int:
        before = self.data.health
        self.data.health = min(self.data.health + amount, self.data.max_health)
        return self.data.health - before

    @property
    def is_defending(self) -> bool:
        return self._defending

    def defend(self) -> None:
        self._defending = True

    def reset_defense(self) -> None:
        self._defending = False

    def learn_ability(self, ability: "Ability") -> None:
        self._abilities[ability.name] = ability

    def has_ability(self, name: str) -> bool:
        return name in self._abilities

    def get_ability(self, name: str) -> "Ability":
        try:
            return self._abilities[name]
        except KeyError:
            raise ValueError(f"{self.name} does not know '{name}'") from None

    def can_equip(self, item: "Item") -> bool:
        """A typed item (e.g. a "Sword") only fits a character trained
        in that weapon type. Untyped items, or characters without a
        weapon type, have no restriction."""
        item_type = item.data.item_type
        own_type = self.data.weapon_type
        return not item_type or not own_type or item_type == own_type

    def equip(self, item: "Item") -> None:
        if not self.can_equip(item):
            raise ValueError(
                f"{self.name} cannot equip {item.name}: "
                f"needs {self.data.weapon_type}, item is {item.data.item_type}"
            )
        self._equipment.append(item)
        for stat, bonus in item.stat_modifiers.items():
            if stat == "health":
                self.data.max_health += bonus
                self.data.health += bonus
            elif stat == "armor":
                self.data.armor += bonus
            elif stat == "attack_power":
                self.data.attack_power += bonus
            else:
                raise ValueError(f"Unknown stat modifier: {stat}")
        if item.granted_ability is not None:
            self.learn_ability(item.granted_ability)

    # -- MEMENTO: originator side ----------------------------------------------

    def save_state(self) -> CharacterMemento:
        """Snapshot everything an action can change: stats (inside the
        data model), known abilities, equipment and the defend flag.
        Items and abilities are shared, unmodified objects, so copying
        the containers that hold them is enough."""
        return CharacterMemento(
            replace(self.data),
            dict(self._abilities),
            list(self._equipment),
            self._defending,
        )

    def restore_state(self, memento: CharacterMemento) -> None:
        self.data = replace(memento._data)
        self._abilities = dict(memento._abilities)
        self._equipment = list(memento._equipment)
        self._defending = memento._defending

    def clone(self) -> "Character":
        """An independent copy (own stats; shared, immutable items and
        abilities). Used for battles, so the catalog stays untouched."""
        copy = Character(replace(self.data))
        copy.restore_state(self.save_state())
        return copy

    def restore_equipment(self, item: "Item") -> None:
        """Attach an item without re-applying its stat modifiers.

        Used only by the Data layer when loading a saved character: its
        CharacterData already reflects every bonus that was in effect
        when it was saved, so calling equip() again would double-apply
        them. Gameplay code should always use equip(), never this."""
        self._equipment.append(item)

    def render(self, renderer: IRenderer) -> None:
        data = self.data
        renderer.title(f"{self.name} — {data.title}" if data.title else self.name)
        renderer.meter("HP", self.health, self.max_health)
        renderer.field("Armor", self.armor)
        renderer.field("Attack", self.attack_power)
        for label, value in (("Vision", data.vision), ("Weapon", data.weapon_type),
                             ("Rarity", "★" * data.rarity), ("Nation", data.nation)):
            if value:
                renderer.field(label, value)
        if data.description:
            renderer.text(data.description)
        renderer.bullet_list(list(self.abilities) or ["(none)"], label="Abilities")
        renderer.bullet_list([item.name for item in self.equipment] or ["(none)"], label="Equipment")
        for kind, url in data.images.items():
            renderer.link(kind, url)

    def __str__(self) -> str:
        return (f"{self.name} [HP: {self.health}/{self.max_health}, "
                f"Armor: {self.armor}, Attack: {self.attack_power}]")
