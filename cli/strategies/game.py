"""Game strategies.

GameStrategy (main mode): pick characters, start / resume a battle,
show saved results.

BattleStrategy (battle mode): the main game loop. `game start` pushes a
"battle" Mode onto the CLI, so while fighting the prompt changes and
only battle actions (plus help/back/exit) are available. When the
battle ends, its result is stored and the mode is popped.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable

from core.game import Battle, Character, EnemyAI, Game

from ..framework import CLI, Args, Command, CommandError, CommandGroup, ICommandStrategy, Mode, UsageError
from ..state import CharactersContext


# -- battle mode -----------------------------------------------------------------------


class BattleSession:
    """Links one Battle to the CLI: after every action shows the state,
    and when the battle is over saves the result and leaves the mode."""

    def __init__(self, ctx: CharactersContext, battle: Battle) -> None:
        self.ctx = ctx
        self.battle = battle

    def after_action(self, cli: CLI) -> None:
        if self.battle.is_over:
            self.finish(cli)
            return
        hero = self.battle.current_hero
        enemies = ", ".join(f"{i}) {e.name} {e.health}/{e.max_health}"
                            for i, e in enumerate(self.battle.enemies, 1) if e.is_alive)
        cli.info(f"Round {self.battle.round} · {hero.name}'s turn "
                 f"(HP {hero.health}/{hero.max_health}) · enemies: {enemies}")

    def finish(self, cli: CLI) -> None:
        result = self.battle.result()
        cli.display(result)
        self.ctx.results.append(result)
        cli.success(f"Result saved to {self.ctx.results.path}")
        cli.pop_mode()

    def close(self) -> None:
        self.battle.close()


class _BattleCommand(Command):
    #: False for commands that do not use up the hero's turn
    takes_turn = True

    def __init__(self, session: BattleSession) -> None:
        self._session = session

    @property
    def battle(self) -> Battle:
        return self._session.battle

    def _enemy(self, ref: str | None) -> Character | None:
        if ref is None:
            return next((e for e in self.battle.enemies if e.is_alive), None)
        target = self.battle.find(ref, self.battle.enemies)
        if target is None:
            raise CommandError(f"No enemy '{ref}'. Use its number from 'status'.")
        return target

    def run(self, args: Args, cli: CLI) -> None:
        super().run(args, cli)
        if self.takes_turn:
            self._session.after_action(cli)


class StatusCommand(_BattleCommand):
    name = "status"
    description = "show both teams, whose turn it is and the abilities"
    aliases = ("st",)
    takes_turn = False

    def execute(self, args: Args, cli: CLI) -> None:
        cli.display(self.battle)


class AttackCommand(_BattleCommand):
    name = "attack"
    usage = "[enemy#]"
    description = "basic attack (default target: first enemy standing)"
    aliases = ("a",)

    def execute(self, args: Args, cli: CLI) -> None:
        self.battle.attack(self._enemy(args.arg(0)))


class SkillCommand(_BattleCommand):
    name = "skill"
    usage = "<ability#|name> [enemy#]"
    description = "use one of the current hero's abilities"
    aliases = ("s",)
    min_args = 1

    def execute(self, args: Args, cli: CLI) -> None:
        hero = self.battle.current_hero
        ref = args.positional[0]
        if ref.isdigit():
            index = int(ref) - 1
            if not 0 <= index < len(hero.abilities):
                count = len(hero.abilities)
                raise CommandError(f"{hero.name} knows {count} abilit{'y' if count == 1 else 'ies'}: "
                                   f"use a number from 1 to {count}.")
            ref = hero.abilities[index]
        self.battle.use_ability(ref, self._enemy(args.arg(1)))


class HealCommand(_BattleCommand):
    name = "heal"
    usage = "[ally#]"
    description = "heal yourself or an ally (amount depends on attack)"
    aliases = ("h",)

    def execute(self, args: Args, cli: CLI) -> None:
        ref = args.arg(0)
        ally = None if ref is None else self.battle.find(ref, self.battle.heroes)
        if ref is not None and ally is None:
            raise CommandError(f"No ally '{ref}'.")
        self.battle.heal(ally)


class DefendCommand(_BattleCommand):
    name = "defend"
    description = "halve incoming damage until your next turn"
    aliases = ("d",)

    def execute(self, args: Args, cli: CLI) -> None:
        hero = self.battle.current_hero
        if hero is not None:
            cli.info(f"{hero.name} takes a defensive stance.")
        self.battle.defend()


class FleeCommand(_BattleCommand):
    name = "flee"
    description = "run away (the battle counts as fled)"

    def execute(self, args: Args, cli: CLI) -> None:
        if not args.has("yes", "y") and not cli.dialog.confirm("Flee from the battle?"):
            raise CommandError("You stay and fight.")
        self.battle.flee()


class BattleSaveCommand(_BattleCommand):
    name = "save"
    usage = "[path.json]"
    description = "save the battle to continue later with 'game resume'"
    takes_turn = False

    def execute(self, args: Args, cli: CLI) -> None:
        path = args.arg(0, self._session.ctx.battle_path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._session.ctx.battles.save(path, self.battle)
        cli.success(f"Battle saved to {path}")


class BattleStrategy(ICommandStrategy):
    name = "battle"
    title = "Battle actions"

    def __init__(self, session: BattleSession) -> None:
        self._commands = [cls(session) for cls in (StatusCommand, AttackCommand, SkillCommand, HealCommand,
                                                   DefendCommand, FleeCommand, BattleSaveCommand)]

    def commands(self) -> Iterable[Command]:
        return self._commands


def enter_battle(cli: CLI, ctx: CharactersContext, battle: Battle) -> None:
    session = BattleSession(ctx, battle)
    cli.push_mode(Mode("battle", "battle> ", [BattleStrategy(session)], on_leave=session.close))
    cli.success("The battle begins! Type 'help' for actions, 'status' to look around.")
    cli.display(battle)


# -- main mode: game ---------------------------------------------------------------------


class _GameCommand(Command):
    def __init__(self, ctx: CharactersContext, rng: random.Random) -> None:
        self._ctx = ctx
        self._rng = rng

    def _roster(self) -> list[tuple[str, Character]]:
        return [(k, c) for k, c in self._ctx.catalog.unique_entries(self._ctx.catalog.characters) if c.is_alive]


class RosterCommand(_GameCommand):
    name = "roster"
    description = "characters available for a game"

    def execute(self, args: Args, cli: CLI) -> None:
        roster = self._roster()
        cli.table(["ID", "Name", "HP", "Armor", "Attack", "Abilities"],
                  [[k, c.name, c.max_health, c.armor, c.attack_power, len(c.abilities)] for k, c in roster])
        if not roster:
            cli.info("No characters yet: 'create char' or 'db create <slug>'.")


class StartCommand(_GameCommand):
    name = "start"
    usage = "[--team c1,c2] [--enemies c3|random] [--count n]"
    description = "choose a team and enemies, then start the battle"

    def execute(self, args: Args, cli: CLI) -> None:
        if cli.mode.name == "battle":
            raise CommandError("A battle is already running.")
        roster = self._roster()
        if not roster:
            raise CommandError("No characters to play with: 'create char' or 'db create <slug>' first.")
        team_ids = args.list_option("team")
        if not team_ids:
            RosterCommand(self._ctx, self._rng).execute(args, cli)
            team_ids = self._ask_ids(cli, "Your team (ids, comma separated)")
        team = [self._ctx.catalog.require_character(key) for key in team_ids]

        enemy_ids = args.list_option("enemies", "e")
        if not enemy_ids:
            enemy_ids = self._ask_ids(cli, "Enemies (ids, or 'random')", default="random")
        enemies = (self._random_enemies(cli, args.int_option("count", default=len(team)))
                   if enemy_ids == ["random"]
                   else [self._ctx.catalog.require_character(key) for key in enemy_ids])

        if set(map(id, team)) & set(map(id, enemies)):
            raise CommandError("A character cannot fight on both sides.")
        battle = Battle(Game(cli.as_displayer()), team, enemies, EnemyAI(self._rng))
        enter_battle(cli, self._ctx, battle)

    def _ask_ids(self, cli: CLI, prompt: str, default: str | None = None) -> list[str]:
        raw = cli.dialog.ask(prompt, default)
        return [part.strip() for part in raw.split(",") if part.strip()]

    def _random_enemies(self, cli: CLI, count: int) -> list[Character]:
        service = self._ctx.service
        if service is None:
            pool = [c for _, c in self._roster()]
            return [self._rng.choice(pool) for _ in range(max(1, count))]
        slugs = service.list_characters()
        enemies = [service.create_character(self._rng.choice(slugs)) for _ in range(max(1, count))]
        cli.info("Enemies from the database: " + ", ".join(e.name for e in enemies))
        return enemies


class ResumeCommand(_GameCommand):
    name = "resume"
    usage = "[path.json]"
    description = "continue a saved battle"

    def execute(self, args: Args, cli: CLI) -> None:
        if cli.mode.name == "battle":
            raise CommandError("A battle is already running.")
        path = args.arg(0, self._ctx.battle_path)
        if not Path(path).is_file():
            raise CommandError(f"No saved battle at {path}")
        battle = self._ctx.battles.load(path, Game(cli.as_displayer()), EnemyAI(self._rng))
        enter_battle(cli, self._ctx, battle)


class ResultsCommand(_GameCommand):
    name = "results"
    usage = "[--last n]"
    description = "history of finished battles"

    def execute(self, args: Args, cli: CLI) -> None:
        results = self._ctx.results.all()
        last = args.int_option("last", default=10)
        if last < 1:
            raise UsageError("--last must be positive")
        shown = results[-last:]
        cli.table(["#", "When", "Outcome", "Rounds", "Team", "Enemies", "Dealt", "Taken"],
                  [[len(results) - len(shown) + i, r.finished_at.replace("T", " "), r.outcome, r.rounds,
                    ", ".join(r.heroes), ", ".join(r.enemies), r.damage_dealt, r.damage_taken]
                   for i, r in enumerate(shown, 1)])
        wins = sum(r.outcome == "victory" for r in results)
        cli.info(f"{len(results)} battle(s), {wins} victor{'y' if wins == 1 else 'ies'}.")


class GameStrategy(ICommandStrategy):
    name = "game"
    title = "Text game"

    def __init__(self, ctx: CharactersContext, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        sub = [cls(ctx, rng) for cls in (RosterCommand, StartCommand, ResumeCommand, ResultsCommand)]
        self._commands = [CommandGroup("game", "turn-based battle with your characters", sub)]

    def commands(self) -> Iterable[Command]:
        return self._commands
