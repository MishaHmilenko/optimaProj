"""Pure data models for the game system.

CharacterData/ItemData/AbilityData hold only plain fields - no methods
that do anything beyond represent the object's state. They double as
the persistence shape (Data layer / "Entities"): items and abilities
reference each other by name (like a foreign key) rather than holding
live objects, so they serialize to JSON without any custom logic.

The descriptive fields (title, vision, weapon_type, rarity, ...) were
added to carry the information that comes from the remote character
database. They all have defaults, so characters created by hand or
loaded from older save files keep working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CharacterData:
    name: str
    max_health: int
    health: int
    armor: int
    attack_power: int
    title: str = ""
    vision: str = ""
    weapon_type: str = ""
    rarity: int = 0
    nation: str = ""
    description: str = ""
    slug: str = ""
    images: dict[str, str] = field(default_factory=dict)


@dataclass
class ItemData:
    name: str
    stat_modifiers: dict[str, int] = field(default_factory=dict)
    granted_ability_name: str | None = None
    item_type: str = ""
    rarity: int = 0
    description: str = ""
    images: dict[str, str] = field(default_factory=dict)


@dataclass
class AbilityData:
    """kind is the AbilityKind value (e.g. "fireball"); params are the
    constructor arguments that particular kind needs."""

    kind: str
    name: str
    params: dict[str, str] = field(default_factory=dict)
