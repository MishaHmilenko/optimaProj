"""Infrastructure strategies: talking to the remote character database
(`db ...`) and persisting the catalog (`save`, `load`)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..framework import CLI, Args, Command, CommandError, CommandGroup, ICommandStrategy, UsageError
from ..state import CharactersContext
from .catalog_info import stars


def _columns(cli: CLI, names: list[str], columns: int = 4) -> None:
    if not names:
        cli.info("(nothing found)")
        return
    width = max(len(n) for n in names) + 2
    for start in range(0, len(names), columns):
        cli.display("  " + "".join(n.ljust(width) for n in names[start:start + columns]).rstrip())
    cli.info(f"{len(names)} total")


class _DbCommand(Command):
    def __init__(self, ctx: CharactersContext) -> None:
        if ctx.service is None:
            raise ValueError("database commands need a GenshinService")
        self._ctx = ctx
        self._service = ctx.service


class DbRefresh(_DbCommand):
    name = "refresh"
    usage = "[--weapons]"
    description = "drop the cache and download the full character list (with details)"

    def execute(self, args: Args, cli: CLI) -> None:
        self._service.refresh()
        slugs = self._service.list_characters()
        bar = cli.progress(len(slugs), "characters")
        failed = []
        for slug in slugs:
            try:
                self._service.character_info(slug)
            except Exception:  # one broken entry must not stop the refresh
                failed.append(slug)
            bar.advance(label=slug)
        bar.finish("characters")
        if args.has("weapons"):
            weapons = self._service.list_weapons()
            bar = cli.progress(len(weapons), "weapons")
            for slug in weapons:
                try:
                    self._service.weapon_info(slug)
                except Exception:
                    failed.append(slug)
                bar.advance(label=slug)
            bar.finish("weapons")
        cli.success(f"Database refreshed: {len(slugs) - len(failed)} character(s) loaded.")
        if failed:
            cli.warn(f"Could not load: {', '.join(failed)}")


class DbChars(_DbCommand):
    name = "chars"
    usage = "[--filter text]"
    description = "list characters available in the database"

    def execute(self, args: Args, cli: CLI) -> None:
        slugs = self._service.list_characters(args.option("filter", "f"))
        infos = [self._service.cached_character(s) for s in slugs]
        if slugs and all(infos):
            cli.table(["Slug", "Name", "Vision", "Weapon", "Rarity", "Nation"],
                      [[i.slug, i.name, i.vision, i.weapon_type, stars(i.rarity), i.nation] for i in infos])
            cli.info(f"{len(slugs)} total")
        else:
            _columns(cli, slugs)
            if slugs:
                cli.info("Run 'db refresh' to load details for the table view.")


class DbWeapons(_DbCommand):
    name = "weapons"
    usage = "[--filter text]"
    description = "list weapons available in the database"

    def execute(self, args: Args, cli: CLI) -> None:
        slugs = self._service.list_weapons(args.option("filter", "f"))
        infos = [self._service.cached_weapon(s) for s in slugs]
        if slugs and all(infos):
            cli.table(["Slug", "Name", "Type", "Rarity", "Base ATK"],
                      [[i.slug, i.name, i.type, stars(i.rarity), i.base_attack] for i in infos])
        else:
            _columns(cli, slugs)


class DbShow(_DbCommand):
    name = "show"
    usage = "<char|weapon> <slug>"
    description = "details from the database, including links to artwork"
    min_args = 2

    def execute(self, args: Args, cli: CLI) -> None:
        kind, slug = args.positional[:2]
        if kind == "char":
            cli.display(self._service.character_info(slug))
        elif kind == "weapon":
            cli.display(self._service.weapon_info(slug))
        else:
            raise UsageError("first argument must be 'char' or 'weapon'")


class DbCreate(_DbCommand):
    name = "create"
    usage = "<slug>"
    description = "add a character from the database to your catalog"
    min_args = 1

    def execute(self, args: Args, cli: CLI) -> None:
        character = self._service.create_character(args.positional[0])
        key = self._ctx.catalog.add_character(character)
        cli.success(f"Created {character.name} as [{key}] — {character}")


class DbEquip(_DbCommand):
    name = "equip"
    usage = "<char_id> <weapon_slug>"
    description = "give a database weapon to a catalog character"
    min_args = 2

    def execute(self, args: Args, cli: CLI) -> None:
        character = self._ctx.catalog.require_character(args.positional[0])
        weapon = self._service.create_weapon(args.positional[1])
        if not character.can_equip(weapon):
            raise CommandError(f"{character.name} cannot equip {weapon.name}: "
                               f"needs {character.data.weapon_type}, weapon is {weapon.data.item_type}.")
        key = self._ctx.catalog.add_item(weapon)
        character.equip(weapon)
        cli.success(f"{character.name} equips {weapon.name} [{key}] — {character}")


class DatabaseStrategy(ICommandStrategy):
    name = "database"
    title = "Remote database"

    def __init__(self, ctx: CharactersContext) -> None:
        sub = [cls(ctx) for cls in (DbRefresh, DbChars, DbWeapons, DbShow, DbCreate, DbEquip)]
        self._commands = [CommandGroup("db", "remote character database (genshin.jmp.blue)", sub)]

    def commands(self) -> Iterable[Command]:
        return self._commands


# -- storage -----------------------------------------------------------------------------


class SaveCommand(Command):
    name = "save"
    usage = "[path.json]"
    description = "save the catalog (default: saves/catalog.json)"

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        path = args.arg(0, self._ctx.save_path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        catalog = self._ctx.catalog
        from core.text import TextFactory
        self._ctx.repository.save(
            path,
            characters=list(catalog.unique_entries(catalog.characters)),
            items=list(catalog.unique_entries(catalog.items)),
            abilities=list(catalog.unique_entries(catalog.abilities)),
            document=TextFactory().create_document(),
        )
        catalog.dirty = False
        cli.success(f"Saved catalog to {path}")


class LoadCommand(Command):
    name = "load"
    usage = "[path.json]"
    description = "load a saved catalog (replaces the current one)"

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        path = args.arg(0, self._ctx.save_path)
        if not Path(path).is_file():
            raise CommandError(f"No such file: {path}")
        state = self._ctx.repository.load(path)
        catalog = self._ctx.catalog
        catalog.clear()
        for key, ability in state["abilities"]:
            catalog.add_ability(ability, display_id=key)
        for key, item in state["items"]:
            catalog.add_item(item, display_id=key)
        for key, character in state["characters"]:
            catalog.add_character(character, display_id=key)
        catalog.dirty = False
        cli.success(f"Loaded {len(state['characters'])} character(s) from {path}")


class StorageStrategy(ICommandStrategy):
    name = "storage"
    title = "Storage"

    def __init__(self, ctx: CharactersContext) -> None:
        self._commands = [SaveCommand(ctx), LoadCommand(ctx)]

    def commands(self) -> Iterable[Command]:
        return self._commands
