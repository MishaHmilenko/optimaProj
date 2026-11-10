"""Transforming strategy: commands that change the catalog or the
characters in it (create via dialog, equip/teach, act, undo, rm)."""

from __future__ import annotations

from typing import Iterable

from core.game import AbilityFactory, AbilityKind, Character, CharacterData, Item, ItemData

from ..framework import CLI, Args, Command, CommandError, ICommandStrategy, UsageError
from ..state import CharactersContext

WEAPON_TYPES = ["Sword", "Claymore", "Polearm", "Bow", "Catalyst"]
VISIONS = ["Anemo", "Cryo", "Dendro", "Electro", "Geo", "Hydro", "Pyro"]


def _optional(options: list[str]):
    """Converter for Dialog.ask: '-' or empty means 'no value'."""
    lowered = {o.lower(): o for o in options}

    def convert(raw: str) -> str:
        if raw in ("", "-"):
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw.lower() in lowered:
            return lowered[raw.lower()]
        raise ValueError(raw)

    return convert


class CreateCommand(Command):
    name = "create"
    usage = "<char|item|ability>"
    description = "create a new character / item / ability through a dialog"
    min_args = 1

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        handlers = {"char": self._character, "item": self._item, "ability": self._ability}
        handler = handlers.get(args.positional[0])
        if handler is None:
            raise UsageError(f"unknown create target '{args.positional[0]}'")
        handler(cli)

    def _character(self, cli: CLI) -> None:
        d = cli.dialog
        catalog = self._ctx.catalog
        cli.info("New character (Enter keeps the default in brackets, '-' skips optional fields)")
        name = d.ask("Name", validate=lambda v: "name is already taken" if catalog.find_character(v) else None)
        health = d.ask_int("Health", 100, minimum=1, maximum=100_000)
        armor = d.ask_int("Armor", 0, minimum=0, maximum=10_000)
        attack = d.ask_int("Attack power", 10, minimum=1, maximum=10_000)
        weapon = d.ask(f"Weapon type ({'/'.join(WEAPON_TYPES)})", "-", _optional(WEAPON_TYPES))
        vision = d.ask(f"Vision ({'/'.join(VISIONS)})", "-", _optional(VISIONS))
        image = d.ask("Image URL or file path", "-", lambda raw: "" if raw == "-" else raw)
        data = CharacterData(name, health, health, armor, attack, weapon_type=weapon, vision=vision,
                             images={"image": image} if image else {})
        key = catalog.add_character(Character(data))
        cli.success(f"Created character '{name}' as [{key}].")

    def _item(self, cli: CLI) -> None:
        d = cli.dialog
        name = d.ask("Item name")
        cli.info("Stat modifiers (0 = no bonus)")
        modifiers = {}
        for stat in ("health", "armor", "attack_power"):
            bonus = d.ask_int(f"{stat} bonus", 0, minimum=-1000, maximum=1000)
            if bonus:
                modifiers[stat] = bonus
        item_type = d.ask(f"Weapon type ({'/'.join(WEAPON_TYPES)}, '-' = any)", "-", _optional(WEAPON_TYPES))
        key = self._ctx.catalog.add_item(Item(ItemData(name, stat_modifiers=modifiers, item_type=item_type)))
        cli.success(f"Created item '{name}' as [{key}].")

    def _ability(self, cli: CLI) -> None:
        d = cli.dialog
        # talents only come from the remote database, so they are not offered here
        kind = AbilityKind(d.choose("Ability type", [k.value for k in AbilityKind if k is not AbilityKind.TALENT]))
        params: dict[str, str] = {}
        if kind is AbilityKind.POWER_STRIKE:
            params["bonus_damage"] = str(d.ask_int("Bonus damage", 10, minimum=1))
        elif kind is AbilityKind.FIREBALL:
            params["damage"] = str(d.ask_int("Damage", 25, minimum=1))
        elif kind is AbilityKind.HEALING_LIGHT:
            params["amount"] = str(d.ask_int("Heal amount", 15, minimum=1))
        ability = AbilityFactory().create(kind, **params)
        key = self._ctx.catalog.add_ability(ability)
        cli.success(f"Created ability '{ability.name}' as [{key}].")


class AddCommand(Command):
    name = "add"
    usage = "<char_id> <item_id|ability_id>"
    description = "equip an item on / teach an ability to a character"
    aliases = ("equip", "teach")

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        char_id = args.option("char_id") or args.arg(0)
        target_id = args.option("id") or args.arg(1)
        if not char_id or not target_id:
            raise UsageError("character id and item/ability id are required")
        catalog = self._ctx.catalog
        character = catalog.require_character(char_id)
        item = catalog.find_item(target_id)
        if item is not None:
            character.equip(item)  # ValueError (wrong weapon type) is shown by the CLI
            catalog.dirty = True
            cli.success(f"Equipped '{item.name}' on {character.name}.")
            return
        ability = catalog.find_ability(target_id)
        if ability is not None:
            character.learn_ability(ability)
            catalog.dirty = True
            cli.success(f"Taught '{ability.name}' to {character.name}.")
            return
        raise CommandError(f"No item or ability found for id: {target_id}")


class ActCommand(Command):
    name = "act"
    usage = "<attack|heal|ability> <actor> <target> [--id <ability_id>]"
    description = "free-form action between two catalog characters (sandbox)"
    min_args = 3

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        action, actor_id, target_id = args.positional[:3]
        catalog, game = self._ctx.catalog, self._ctx.game
        actor = catalog.require_character(actor_id)
        target = catalog.require_character(target_id)
        for character in (actor, target):
            if character not in game.characters:
                game.add_character(character)
        if action == "attack":
            game.basic_attack(actor, target)
        elif action == "heal":
            game.heal(actor, amount=15, target=target if target is not actor else None)
        elif action == "ability":
            ability_id = args.option("id")
            if not ability_id:
                raise UsageError("act ability needs --id <ability_id>")
            ability = catalog.find_ability(ability_id)
            game.use_ability(actor, ability.name if ability is not None else ability_id, target)
        else:
            raise UsageError(f"unknown action '{action}'")
        catalog.dirty = True


class UndoCommand(Command):
    name = "undo"
    description = "undo the last 'act' action (Command + Memento)"

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        # the game announces the undo itself (observer -> displayer)
        if self._ctx.game.undo() is None:
            cli.info("Nothing to undo.")


class RemoveCommand(Command):
    name = "rm"
    usage = "<char_id>"
    description = "remove a character from the catalog (asks for confirmation)"
    min_args = 1

    def __init__(self, ctx: CharactersContext) -> None:
        self._ctx = ctx

    def execute(self, args: Args, cli: CLI) -> None:
        character = self._ctx.catalog.require_character(args.positional[0])
        if not args.has("yes", "y") and not cli.dialog.confirm(f"Remove {character.name}?"):
            cli.info("Cancelled.")
            return
        self._ctx.catalog.remove_character(args.positional[0])
        cli.success(f"Removed {character.name}.")


class CatalogActionStrategy(ICommandStrategy):
    name = "actions"
    title = "Actions (change the catalog)"

    def __init__(self, ctx: CharactersContext) -> None:
        self._commands = [CreateCommand(ctx), AddCommand(ctx), ActCommand(ctx),
                          UndoCommand(ctx), RemoveCommand(ctx)]

    def commands(self) -> Iterable[Command]:
        return self._commands
