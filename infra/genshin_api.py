"""Client for the genshin.dev API (https://genshin.jmp.blue).

Returns DTOs (data transfer models): flat, immutable snapshots of
exactly what the remote service sent, with the JSON keys translated to
our naming. Turning them into game objects is not this module's job -
that happens in services/genshin_mapper.py.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any

from .http_client import IHttpClient, RemoteServiceError
from .rendering import IRenderable, IRenderer

DEFAULT_BASE_URL = "https://genshin.jmp.blue"


@dataclass(frozen=True)
class TalentDto:
    name: str
    unlock: str
    description: str
    type: str


@dataclass(frozen=True)
class CharacterDto(IRenderable):
    slug: str
    name: str
    title: str
    vision: str
    weapon_type: str
    rarity: int
    nation: str
    description: str
    talents: tuple[TalentDto, ...]
    images: tuple[tuple[str, str], ...] = ()

    def render(self, renderer: IRenderer) -> None:
        renderer.title(f"{self.name} — {self.title}" if self.title else self.name)
        renderer.field("Vision", self.vision)
        renderer.field("Weapon", self.weapon_type)
        renderer.field("Rarity", "★" * self.rarity)
        renderer.field("Nation", self.nation)
        renderer.text(self.description)
        renderer.bullet_list([f"{t.name} ({t.unlock})" for t in self.talents], label="Talents")
        for kind, url in self.images:
            renderer.link(kind, url)


@dataclass(frozen=True)
class WeaponDto(IRenderable):
    slug: str
    name: str
    type: str
    rarity: int
    base_attack: int
    sub_stat: str
    passive_name: str
    passive_desc: str
    images: tuple[tuple[str, str], ...] = ()

    def render(self, renderer: IRenderer) -> None:
        renderer.title(self.name)
        renderer.field("Type", self.type)
        renderer.field("Rarity", "★" * self.rarity)
        renderer.field("Base ATK", self.base_attack)
        renderer.field("Sub stat", self.sub_stat)
        if self.passive_name:
            renderer.field(self.passive_name, self.passive_desc)
        for kind, url in self.images:
            renderer.link(kind, url)


CHARACTER_IMAGES = ("icon-big", "card", "gacha-splash")
WEAPON_IMAGES = ("icon",)


class GenshinApiClient:
    def __init__(self, http: IHttpClient, base_url: str = DEFAULT_BASE_URL) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    def _url(self, *parts: str) -> str:
        quoted = [urllib.parse.quote(part, safe="") for part in parts]
        return "/".join([self._base_url, *quoted])

    def _get_list(self, resource: str) -> list[str]:
        payload = self._http.get_json(self._url(resource))
        if not isinstance(payload, list):
            raise RemoteServiceError(f"Expected a list from /{resource}, got {type(payload).__name__}")
        return [str(entry) for entry in payload]

    def _get_object(self, resource: str, slug: str) -> dict[str, Any]:
        payload = self._http.get_json(self._url(resource, slug))
        if not isinstance(payload, dict):
            raise RemoteServiceError(f"Expected an object from /{resource}/{slug}")
        return payload

    def image_urls(self, resource: str, slug: str, kinds: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
        """Links to the artwork the API serves for an entity (it is not
        downloaded - the UI decides whether to open or show it)."""
        return tuple((kind, self._url(resource, slug, kind)) for kind in kinds)

    def list_characters(self) -> list[str]:
        return self._get_list("characters")

    def list_weapons(self) -> list[str]:
        return self._get_list("weapons")

    def get_character(self, slug: str) -> CharacterDto:
        raw = self._get_object("characters", slug)
        talents = tuple(
            TalentDto(
                name=str(entry.get("name", "")),
                unlock=str(entry.get("unlock", "")),
                description=str(entry.get("description", "")),
                type=str(entry.get("type", "")),
            )
            for entry in raw.get("skillTalents", []) or []
        )
        return CharacterDto(
            slug=slug,
            name=str(raw.get("name", slug)),
            title=str(raw.get("title", "")),
            vision=str(raw.get("vision", "")),
            weapon_type=str(raw.get("weapon", "")),
            rarity=int(raw.get("rarity", 0) or 0),
            nation=str(raw.get("nation", "")),
            description=str(raw.get("description", "")),
            talents=talents,
            images=self.image_urls("characters", slug, CHARACTER_IMAGES),
        )

    def get_weapon(self, slug: str) -> WeaponDto:
        raw = self._get_object("weapons", slug)
        return WeaponDto(
            slug=slug,
            name=str(raw.get("name", slug)),
            type=str(raw.get("type", "")),
            rarity=int(raw.get("rarity", 0) or 0),
            base_attack=int(raw.get("baseAttack", 0) or 0),
            sub_stat=str(raw.get("subStat", "")),
            passive_name=str(raw.get("passiveName", "")),
            passive_desc=str(raw.get("passiveDesc", "")),
            images=self.image_urls("weapons", slug, WEAPON_IMAGES),
        )
