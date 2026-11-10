"""Item wraps ItemData; granted_ability stays a live Ability object in
memory (the Data layer resolves it to/from a name when persisting)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infra.rendering import IRenderable, IRenderer

from .models import ItemData

if TYPE_CHECKING:
    from .abilities import Ability


class Item(IRenderable):
    def __init__(self, data: ItemData, granted_ability: "Ability | None" = None) -> None:
        self.data = data
        self._granted_ability = granted_ability

    @property
    def name(self) -> str:
        return self.data.name

    @property
    def stat_modifiers(self) -> dict[str, int]:
        return dict(self.data.stat_modifiers)

    @property
    def granted_ability(self) -> "Ability | None":
        return self._granted_ability

    def render(self, renderer: IRenderer) -> None:
        renderer.title(self.name)
        if self.data.item_type:
            renderer.field("Type", self.data.item_type)
        if self.data.rarity:
            renderer.field("Rarity", "★" * self.data.rarity)
        for stat, bonus in self.stat_modifiers.items():
            renderer.field(stat, f"{bonus:+d}")
        if self.granted_ability is not None:
            renderer.field("Grants", self.granted_ability.name)
        if self.data.description:
            renderer.text(self.data.description)
        for kind, url in self.data.images.items():
            renderer.link(kind, url)

    def __str__(self) -> str:
        return self.data.name
