"""State shared by the characters-mode strategies.

Catalog         id-addressable storage of the user's characters, items
                and abilities (ids like c1, i1, a1; names work too).
CharactersContext  everything the strategies need, passed in once by the
                composition root (cli/app.py) - strategies never build
                their own dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.game import Character, CombatStatistics, Game, Item
from data import BattleRepository, Repository, ResultsRepository
from services import GenshinService

from .framework import CommandError


class Catalog:
    """CLI-only id-addressable storage for characters, items and abilities."""

    def __init__(self) -> None:
        self.characters: dict[str, Character] = {}
        self.items: dict[str, Item] = {}
        self.abilities: dict[str, object] = {}
        self._counters: dict[str, int] = {}
        #: True when there are changes that were not saved yet
        self.dirty = False

    def _next_id(self, prefix: str) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        key = f"{prefix}{self._counters[prefix]}"
        store = {"c": self.characters, "i": self.items, "a": self.abilities}[prefix]
        return key if key not in store else self._next_id(prefix)

    def add_character(self, character: Character, display_id: str | None = None) -> str:
        key = display_id or self._next_id("c")
        self.dirty = True
        self.characters[key] = character
        self.characters.setdefault(character.name, character)
        return key

    def add_item(self, item: Item, display_id: str | None = None) -> str:
        key = display_id or self._next_id("i")
        self.dirty = True
        self.items[key] = item
        self.items.setdefault(item.name, item)
        return key

    def add_ability(self, ability, display_id: str | None = None) -> str:
        key = display_id or self._next_id("a")
        self.dirty = True
        self.abilities[key] = ability
        self.abilities.setdefault(ability.name, ability)
        return key

    def find_character(self, key: str) -> Character | None:
        return self.characters.get(key)

    def find_item(self, key: str) -> Item | None:
        return self.items.get(key)

    def find_ability(self, key: str):
        return self.abilities.get(key)

    def unique_characters(self):
        seen: set[int] = set()
        for character in self.characters.values():
            if id(character) in seen:
                continue
            seen.add(id(character))
            yield character

    def unique_entries(self, store: dict):
        seen: set[int] = set()
        for key, obj in store.items():
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            yield key, obj

    def key_of(self, store: dict, obj: object) -> str:
        """The display id (first key) of an object in a store."""
        return next(key for key, value in store.items() if value is obj)

    def remove_character(self, key: str) -> Character | None:
        character = self.characters.get(key)
        if character is None:
            return None
        for alias in [k for k, v in self.characters.items() if v is character]:
            del self.characters[alias]
        self.dirty = True
        return character

    def require_character(self, key: str) -> Character:
        character = self.find_character(key)
        if character is None:
            raise CommandError(f"No such character: {key}. See 'ls char'.")
        return character

    def clear(self) -> None:
        self.characters.clear()
        self.items.clear()
        self.abilities.clear()
        self._counters.clear()


@dataclass
class CharactersContext:
    catalog: Catalog
    game: Game
    repository: Repository
    service: GenshinService | None = None
    battles: BattleRepository = field(default_factory=BattleRepository)
    results: ResultsRepository = field(default_factory=lambda: ResultsRepository("saves/results.json"))
    stats: CombatStatistics = field(default_factory=CombatStatistics)
    save_path: str = "saves/catalog.json"
    battle_path: str = "saves/battle.json"

    def __post_init__(self) -> None:
        # Observer: statistics are one more subscriber to game events.
        self.game.subscribe(self.stats)
