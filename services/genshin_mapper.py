"""Translates API DTOs (infra) into game objects (core).

Keeping this in its own class means neither side knows about the other:
GenshinApiClient doesn't know what a Character is, and Character
doesn't know the JSON shape of the remote API.
"""

from __future__ import annotations

from core.game import Character, CharacterData, Item, ItemData, TalentAbility
from infra import CharacterDto, WeaponDto

from .stat_generator import StatGenerator


class GenshinMapper:
    WEAPON_ATTACK_DIVISOR = 5

    def __init__(self, stat_generator: StatGenerator) -> None:
        self._stats = stat_generator

    def to_character(self, dto: CharacterDto) -> Character:
        stats = self._stats.generate(dto.rarity)
        character = Character(
            CharacterData(
                name=dto.name,
                max_health=stats.health,
                health=stats.health,
                armor=stats.armor,
                attack_power=stats.attack_power,
                title=dto.title,
                vision=dto.vision,
                weapon_type=dto.weapon_type,
                rarity=dto.rarity,
                nation=dto.nation,
                description=dto.description,
                slug=dto.slug,
                images=dict(dto.images),
            )
        )
        for talent in dto.talents:
            character.learn_ability(TalentAbility.for_type(talent.name, talent.description, talent.type))
        return character

    def to_item(self, dto: WeaponDto) -> Item:
        attack_bonus = max(1, dto.base_attack // self.WEAPON_ATTACK_DIVISOR)
        passive = f"{dto.passive_name}: {dto.passive_desc}" if dto.passive_name else dto.passive_desc
        description = " · ".join(part for part in (dto.sub_stat, passive) if part)
        return Item(
            ItemData(
                name=dto.name,
                stat_modifiers={"attack_power": attack_bonus},
                item_type=dto.type,
                rarity=dto.rarity,
                description=description,
                images=dict(dto.images),
            )
        )
