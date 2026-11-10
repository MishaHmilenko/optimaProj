"""Represents a character as a structured-text document.

Uses DocumentBuilder (Builder pattern) instead of creating and attaching
every heading/paragraph by hand: the sheet's layout reads top to bottom
as the document it produces. The output format is chosen by passing a
TextElementFactory (Abstract Factory) - the building code is identical
for plain text, Markdown and HTML.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.game import Character
from core.text import DocumentBuilder, PlainTextElementFactory, Root, TextElementFactory
from infra import IDisplayable

TALENT_LABELS = {
    "NORMAL_ATTACK": "Normal Attack",
    "ELEMENTAL_SKILL": "Elemental Skill",
    "ELEMENTAL_BURST": "Elemental Burst",
}


def stars(rarity: int) -> str:
    return "★" * rarity


def first_lines(text: str, limit: int = 220) -> str:
    """Talent descriptions are long and multi-line; a sheet only needs
    the gist, so keep the text up to the limit and join lines."""
    flat = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _join(*parts: str) -> str:
    return " · ".join(part for part in parts if part)


class CharacterSheetBuilder:
    def __init__(self, family: TextElementFactory | None = None) -> None:
        self._family = family or PlainTextElementFactory()

    def build(self, character: Character) -> Root:
        data = character.data
        doc = DocumentBuilder(self._family)

        doc.heading(character.name, 1)
        doc.paragraph(_join(data.title, data.vision, data.weapon_type, stars(data.rarity)))
        doc.paragraph(data.description)

        (doc.heading("Stats", 2)
            .paragraph(f"HP: {character.health}/{character.max_health}")
            .paragraph(f"Armor: {character.armor}")
            .paragraph(f"Attack: {character.attack_power}")
            .end())

        doc.heading("Talents", 2)
        abilities = character.abilities_map
        if not abilities:
            doc.paragraph("(no talents)")
        for name, ability in abilities.items():
            label = TALENT_LABELS.get(getattr(ability, "talent_type", ""), type(ability).__name__)
            description = first_lines(getattr(ability, "description", ""))
            doc.heading(name, 3).paragraph(f"[{label}] {description}".rstrip()).end()
        doc.end()

        doc.heading("Equipment", 2)
        if not character.equipment:
            doc.paragraph("(nothing equipped)")
        for item in character.equipment:
            bonuses = ", ".join(f"{stat} +{value}" for stat, value in item.stat_modifiers.items())
            (doc.heading(item.name, 3)
                .paragraph(_join(item.data.item_type, stars(item.data.rarity), bonuses))
                .paragraph(first_lines(item.data.description))
                .end())

        return doc.build()


@dataclass(frozen=True)
class DocumentDisplayable(IDisplayable):
    """Lets any IDisplayer show a text document - full or just its
    table of contents."""

    document: Root
    table_of_contents: bool = False

    def to_display(self) -> str:
        if self.table_of_contents:
            return self.document.table_of_contents()
        return self.document.render()
