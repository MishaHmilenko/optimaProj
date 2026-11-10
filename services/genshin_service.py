"""Facade the CLI talks to: lists what the remote database has and
creates game objects from it. Caches API responses, since the remote
data doesn't change while the program runs and each character/weapon
should only cost one request."""

from __future__ import annotations

from core.game import Character, Item
from infra import CharacterDto, GenshinApiClient, WeaponDto

from .genshin_mapper import GenshinMapper


class GenshinService:
    def __init__(self, api: GenshinApiClient, mapper: GenshinMapper) -> None:
        self._api = api
        self._mapper = mapper
        self._character_slugs: list[str] | None = None
        self._weapon_slugs: list[str] | None = None
        self._characters: dict[str, CharacterDto] = {}
        self._weapons: dict[str, WeaponDto] = {}

    @staticmethod
    def _filter(slugs: list[str], text: str | None) -> list[str]:
        if not text:
            return list(slugs)
        needle = text.lower()
        return [slug for slug in slugs if needle in slug.lower()]

    def list_characters(self, filter_text: str | None = None) -> list[str]:
        if self._character_slugs is None:
            self._character_slugs = self._api.list_characters()
        return self._filter(self._character_slugs, filter_text)

    def list_weapons(self, filter_text: str | None = None) -> list[str]:
        if self._weapon_slugs is None:
            self._weapon_slugs = self._api.list_weapons()
        return self._filter(self._weapon_slugs, filter_text)

    def character_info(self, slug: str) -> CharacterDto:
        if slug not in self._characters:
            self._characters[slug] = self._api.get_character(slug)
        return self._characters[slug]

    def weapon_info(self, slug: str) -> WeaponDto:
        if slug not in self._weapons:
            self._weapons[slug] = self._api.get_weapon(slug)
        return self._weapons[slug]

    def cached_character(self, slug: str) -> CharacterDto | None:
        return self._characters.get(slug)

    def cached_weapon(self, slug: str) -> WeaponDto | None:
        return self._weapons.get(slug)

    def refresh(self) -> None:
        """Forget everything cached, so the next calls hit the API again."""
        self._character_slugs = None
        self._weapon_slugs = None
        self._characters.clear()
        self._weapons.clear()

    def create_character(self, slug: str) -> Character:
        """A new, independent Character every call (fresh stat roll)."""
        return self._mapper.to_character(self.character_info(slug))

    def create_weapon(self, slug: str) -> Item:
        return self._mapper.to_item(self.weapon_info(slug))
