"""Battle: the main loop of the text game, independent of any UI.

A battle is fought in rounds. In every round each living hero gets one
action (chosen by the player); once all heroes have acted, every living
enemy acts automatically (EnemyAI) and a new round begins.

Heroes and enemies are *clones* of catalog characters, so a lost fight
does not damage the user's catalog. Every action still goes through the
Game mediator, so observers (console log, statistics) see it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from infra.rendering import IRenderable, IRenderer

from .character import Character
from .events import CombatStatistics
from .game import Game


class Outcome(str, Enum):
    IN_PROGRESS = "in progress"
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"


@dataclass
class BattleResult(IRenderable):
    outcome: str
    rounds: int
    heroes: list[str]
    enemies: list[str]
    survivors: list[str]
    damage_dealt: int
    damage_taken: int
    finished_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def render(self, renderer: IRenderer) -> None:
        renderer.title(f"Battle result: {self.outcome.upper()}")
        renderer.field("Rounds", self.rounds)
        renderer.field("Team", ", ".join(self.heroes))
        renderer.field("Enemies", ", ".join(self.enemies))
        renderer.field("Survivors", ", ".join(self.survivors) or "-")
        renderer.field("Damage dealt", self.damage_dealt)
        renderer.field("Damage taken", self.damage_taken)
        renderer.field("Finished", self.finished_at)


class EnemyAI:
    """Strategy for enemy turns: hit the weakest hero, sometimes with an
    ability. Separate class so a smarter AI can be swapped in."""

    ABILITY_CHANCE = 0.35

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()

    def act(self, game: Game, enemy: Character, heroes: list[Character]) -> None:
        targets = [hero for hero in heroes if hero.is_alive]
        if not targets:
            return
        target = min(targets, key=lambda hero: hero.health)
        if enemy.abilities and self._rng.random() < self.ABILITY_CHANCE:
            try:
                game.use_ability(enemy, self._rng.choice(enemy.abilities), target)
                return
            except ValueError:
                pass  # e.g. a self-only ability: fall back to a basic attack
        game.basic_attack(enemy, target)


class Battle(IRenderable):
    def __init__(self, game: Game, heroes: list[Character], enemies: list[Character],
                 ai: EnemyAI | None = None, *, clone: bool = True) -> None:
        if not heroes or not enemies:
            raise ValueError("A battle needs at least one hero and one enemy")
        self._game = game
        self.heroes = [hero.clone() if clone else hero for hero in heroes]
        self.enemies = [enemy.clone() if clone else enemy for enemy in enemies]
        self._ai = ai or EnemyAI()
        self.round = 1
        self._acted: set[int] = set()
        self._fled = False
        self._stats = CombatStatistics()
        game.subscribe(self._stats)
        for character in self.heroes + self.enemies:
            game.add_character(character)

    # -- state -------------------------------------------------------------------

    @property
    def outcome(self) -> Outcome:
        if self._fled:
            return Outcome.FLED
        if not any(enemy.is_alive for enemy in self.enemies):
            return Outcome.VICTORY
        if not any(hero.is_alive for hero in self.heroes):
            return Outcome.DEFEAT
        return Outcome.IN_PROGRESS

    @property
    def is_over(self) -> bool:
        return self.outcome is not Outcome.IN_PROGRESS

    @property
    def current_hero(self) -> Character | None:
        for index, hero in enumerate(self.heroes):
            if hero.is_alive and index not in self._acted:
                return hero
        return None

    @property
    def acted_indexes(self) -> set[int]:
        return set(self._acted)

    @property
    def statistics(self) -> CombatStatistics:
        return self._stats

    def restore_progress(self, round_number: int, acted: set[int],
                         damage_dealt: dict[str, int] | None = None,
                         damage_taken: dict[str, int] | None = None) -> None:
        """Used by the Data layer when a saved battle is loaded."""
        self.round = round_number
        self._acted = set(acted)
        self._stats.damage_dealt.update(damage_dealt or {})
        self._stats.damage_taken.update(damage_taken or {})

    def find(self, name_or_index: str, side: list[Character]) -> Character | None:
        if name_or_index.isdigit():
            index = int(name_or_index) - 1
            return side[index] if 0 <= index < len(side) else None
        needle = name_or_index.lower()
        return next((c for c in side if c.name.lower() == needle), None)

    # -- hero actions --------------------------------------------------------------

    def _hero(self) -> Character:
        if self.is_over:
            raise ValueError(f"The battle is over ({self.outcome.value}).")
        hero = self.current_hero
        assert hero is not None
        return hero

    def _alive(self, target: Character | None, side: list[Character], what: str) -> Character:
        if target is None or target not in side:
            raise ValueError(f"Unknown {what}.")
        if not target.is_alive:
            raise ValueError(f"{target.name} is already defeated.")
        return target

    def attack(self, target: Character | None) -> None:
        hero = self._hero()
        self._game.basic_attack(hero, self._alive(target, self.enemies, "enemy"))
        self._end_hero_turn(hero)

    def use_ability(self, ability_name: str, target: Character | None) -> None:
        hero = self._hero()
        ability = next((a for a in hero.abilities if a.lower() == ability_name.lower()), None)
        if ability is None:
            raise ValueError(f"{hero.name} does not know '{ability_name}'.")
        if target is not None and target not in self.enemies + self.heroes:
            raise ValueError("Unknown target.")
        self._game.use_ability(hero, ability, target)
        self._end_hero_turn(hero)

    def heal(self, target: Character | None) -> None:
        hero = self._hero()
        recipient = self._alive(target or hero, self.heroes, "ally")
        if recipient.health >= recipient.max_health:
            raise ValueError(f"{recipient.name} is already at full health.")
        amount = max(10, hero.attack_power // 2)
        self._game.heal(hero, amount, recipient if recipient is not hero else None)
        self._end_hero_turn(hero)

    def defend(self) -> None:
        hero = self._hero()
        hero.defend()
        self._end_hero_turn(hero)

    def flee(self) -> None:
        self._fled = True

    def _end_hero_turn(self, hero: Character) -> None:
        self._acted.add(self.heroes.index(hero))
        if self.current_hero is None and not self.is_over:
            self._enemy_phase()

    def _enemy_phase(self) -> None:
        for enemy in self.enemies:
            if enemy.is_alive and not self.is_over:
                enemy.reset_defense()
                self._ai.act(self._game, enemy, self.heroes)
        if not self.is_over:
            self.round += 1
            self._acted.clear()
            for hero in self.heroes:
                hero.reset_defense()

    # -- results -----------------------------------------------------------------

    def result(self) -> BattleResult:
        hero_names = {hero.name for hero in self.heroes}
        dealt = sum(v for name, v in self._stats.damage_dealt.items() if name in hero_names)
        taken = sum(v for name, v in self._stats.damage_taken.items() if name in hero_names)
        return BattleResult(
            outcome=self.outcome.value,
            rounds=self.round,
            heroes=[hero.name for hero in self.heroes],
            enemies=[enemy.name for enemy in self.enemies],
            survivors=[hero.name for hero in self.heroes if hero.is_alive],
            damage_dealt=dealt,
            damage_taken=taken,
        )

    def close(self) -> None:
        self._game.unsubscribe(self._stats)

    def render(self, renderer: IRenderer) -> None:
        current = self.current_hero
        renderer.title(f"Round {self.round} — {self.outcome.value}")

        def rows(side: list[Character]) -> list[list[object]]:
            return [
                [i, ("> " if c is current else "  ") + c.name, f"{c.health}/{c.max_health}",
                 c.armor, c.attack_power, "defeated" if not c.is_alive else "ok"]
                for i, c in enumerate(side, start=1)
            ]

        renderer.text("Your team:")
        renderer.table(["#", "Hero", "HP", "Armor", "Attack", "State"], rows(self.heroes))
        renderer.text("Enemies:")
        renderer.table(["#", "Enemy", "HP", "Armor", "Attack", "State"], rows(self.enemies))
        if current is not None:
            renderer.field("Turn", current.name)
            renderer.bullet_list(list(current.abilities) or ["(none)"], label="Abilities")
