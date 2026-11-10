"""Output strategy: commands that only *show* information
(ls, show, sheet, stats). None of them changes any state."""

from __future__ import annotations

from typing import Iterable

from core.text import factory_for
from infra import IRenderable
from services import CharacterSheetBuilder, DocumentDisplayable

from ..framework import CLI, Args, Command, CommandError, ICommandStrategy, UsageError
from ..state import CharactersContext


def stars(rarity: int) -> str:
    return "★" * rarity


class ListCommand(Command):
    name = "ls"
    usage = "[char|item|ability] [--filter text]"
    description = "list characters (default), items or abilities in the catalog"

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        category = args.arg(0, "char")
        needle = (args.option("filter", "f") or "").lower()
        catalog = self._ctx.catalog
        listers = {"char": self._characters, "item": self._items, "ability": self._abilities}
        if category not in listers:
            raise UsageError(f"unknown category '{category}'")
        if args.has("id"):  # legacy form: ls char --id c1
            cli.display(_find_any(self._ctx, args.option("id") or ""))
            return
        listers[category](cli, [(k, o) for k, o in catalog.unique_entries(self._store(category))
                                if needle in o.name.lower()])

    def _store(self, category: str) -> dict:
        catalog = self._ctx.catalog
        return {"char": catalog.characters, "item": catalog.items, "ability": catalog.abilities}[category]

    def _characters(self, cli: CLI, entries: list) -> None:
        cli.table(
            ["ID", "Name", "HP", "Armor", "Attack", "Vision", "Weapon", "Rarity"],
            [[k, c.name, f"{c.health}/{c.max_health}", c.armor, c.attack_power,
              c.data.vision, c.data.weapon_type, stars(c.data.rarity)] for k, c in entries],
        )
        cli.info(f"{len(entries)} character(s). 'show <id>' for details.")

    def _items(self, cli: CLI, entries: list) -> None:
        catalog = self._ctx.catalog
        rows = []
        for key, item in entries:
            bonuses = ", ".join(f"{s} {b:+d}" for s, b in item.stat_modifiers.items())
            holders = [c.name for c in catalog.unique_characters() if item in c.equipment]
            rows.append([key, item.name, item.data.item_type, bonuses, ", ".join(holders) or "-"])
        cli.table(["ID", "Name", "Type", "Bonuses", "Used by"], rows)

    def _abilities(self, cli: CLI, entries: list) -> None:
        catalog = self._ctx.catalog
        rows = [[key, ability.name, ", ".join(c.name for c in catalog.unique_characters()
                                              if ability.name in c.abilities) or "-"]
                for key, ability in entries]
        cli.table(["ID", "Name", "Known by"], rows)


def _find_any(ctx: CharactersContext, key: str) -> object:
    catalog = ctx.catalog
    found = catalog.find_character(key) or catalog.find_item(key) or catalog.find_ability(key)
    if found is None:
        raise CommandError(f"Nothing in the catalog with id or name '{key}'.")
    return found


class ShowCommand(Command):
    name = "show"
    usage = "<id|name>"
    description = "general information about a character, item or ability (with artwork links)"
    min_args = 1

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        found = _find_any(self._ctx, " ".join(args.positional))
        if isinstance(found, IRenderable):
            cli.display(found)
        else:  # abilities: a name and, for talents, a description
            cli.display(cli.style(found.name, "bold", "cyan"))
            cli.renderer.text(getattr(found, "description", ""))


class SheetCommand(Command):
    name = "sheet"
    usage = "<char_id> [--toc] [--format plain|markdown|html]"
    description = "character sheet built with the structured-text system"
    min_args = 1

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        character = self._ctx.catalog.require_character(args.positional[0])
        family = factory_for(args.option("format", default="plain") or "plain")
        document = CharacterSheetBuilder(family).build(character)
        cli.display(DocumentDisplayable(document, table_of_contents=args.has("toc")))


class StatsCommand(Command):
    name = "stats"
    description = "damage / healing statistics per character"

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        cli.display(self._ctx.stats)


class CatalogInfoStrategy(ICommandStrategy):
    name = "info"
    title = "Information (read-only)"

    def __init__(self, ctx: CharactersContext) -> None:
        self._commands = [ListCommand(ctx), ShowCommand(ctx), SheetCommand(ctx), StatsCommand(ctx)]

    def commands(self) -> Iterable[Command]:
        return self._commands
