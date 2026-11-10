"""Converts the game catalog (characters, items, abilities) to/from a
plain JSON-serializable structure.

Items and abilities are embedded by reference (name), the same way a
relational schema would use a foreign key instead of duplicating rows -
see the CharacterItems example from the lecture. On load, we rebuild
abilities and items first, then characters, then re-attach by name.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from core.game import AbilityFactory, Character, CharacterData, Item, ItemData
from core.game.models import AbilityData


def abilities_to_list(entries: Iterable[tuple[str, Any]]) -> list[dict]:
    result = []
    for key, ability in entries:
        data = ability.to_data()
        result.append({"id": key, **asdict(data)})
    return result


def items_to_list(entries: Iterable[tuple[str, Item]]) -> list[dict]:
    result = []
    for key, item in entries:
        entry = {"id": key, "data": asdict(item.data)}
        if item.granted_ability is not None:
            entry["granted_ability_name"] = item.granted_ability.name
        result.append(entry)
    return result


def characters_to_list(entries: Iterable[tuple[str, Character]]) -> list[dict]:
    result = []
    for key, character in entries:
        result.append({
            "id": key,
            "data": asdict(character.data),
            "ability_names": list(character.abilities),
            "item_names": [item.name for item in character.equipment],
        })
    return result


def _with_reachable(listed: Iterable[tuple[str, Any]], reachable: Iterable[Any], prefix: str) -> list[tuple[str, Any]]:
    """Listed (id, obj) pairs plus any object reachable from characters
    that wasn't listed (e.g. talents a character got straight from the
    remote database). Without this they would be lost on reload."""
    result = list(listed)
    seen = {id(obj) for _, obj in result}
    counter = 0
    for obj in reachable:
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        counter += 1
        result.append((f"{prefix}{counter}", obj))
    return result


def catalog_to_dict(
    characters: Iterable[tuple[str, Character]],
    items: Iterable[tuple[str, Item]],
    abilities: Iterable[tuple[str, Any]],
) -> dict:
    characters = list(characters)
    all_items = _with_reachable(
        items, (item for _, c in characters for item in c.equipment), "auto_i"
    )
    reachable_abilities = [a for _, c in characters for a in c.abilities_map.values()]
    reachable_abilities += [item.granted_ability for _, item in all_items if item.granted_ability]
    all_abilities = _with_reachable(abilities, reachable_abilities, "auto_a")
    return {
        "characters": characters_to_list(characters),
        "items": items_to_list(all_items),
        "abilities": abilities_to_list(all_abilities),
    }


def catalog_from_dict(data: dict) -> tuple[list[tuple[str, Character]], list[tuple[str, Item]], list[tuple[str, Any]]]:
    """Rebuild (id, object) lists for characters/items/abilities in an
    order that respects their dependencies (abilities -> items -> characters)."""
    factory = AbilityFactory()

    abilities: list[tuple[str, Any]] = []
    abilities_by_name: dict[str, Any] = {}
    for entry in data.get("abilities", []):
        ability = factory.from_data(AbilityData(kind=entry["kind"], name=entry["name"], params=entry["params"]))
        abilities.append((entry["id"], ability))
        abilities_by_name[ability.name] = ability

    items: list[tuple[str, Item]] = []
    items_by_name: dict[str, Item] = {}
    for entry in data.get("items", []):
        item_data = ItemData(**entry["data"])
        granted_name = entry.get("granted_ability_name")
        granted_ability = abilities_by_name.get(granted_name) if granted_name else None
        item = Item(item_data, granted_ability=granted_ability)
        items.append((entry["id"], item))
        items_by_name[item.name] = item

    characters: list[tuple[str, Character]] = []
    for entry in data.get("characters", []):
        character = Character(CharacterData(**entry["data"]))
        for ability_name in entry.get("ability_names", []):
            ability = abilities_by_name.get(ability_name)
            if ability is not None:
                character.learn_ability(ability)
        for item_name in entry.get("item_names", []):
            item = items_by_name.get(item_name)
            if item is not None:
                character.restore_equipment(item)
        characters.append((entry["id"], character))

    return characters, items, abilities
