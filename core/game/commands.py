"""COMMAND: every game action as an object.

Before, each action was just a Game method that changed characters on
the spot. Now an action is an object that carries everything needed to
run it (who, on whom, with what) and can be executed later, kept in a
history and undone.

Undo uses the MEMENTO pattern: right before running, a command asks
every character it is about to affect for a snapshot (save_state) and
restores them on undo(). The command never looks inside the snapshots,
so Character's state stays encapsulated.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .character import Character, CharacterMemento
from .items import Item


class GameCommand(ABC):
    def __init__(self) -> None:
        self._snapshots: list[tuple[Character, CharacterMemento]] = []
        self._health_changes: dict[Character, int] = {}
        self._message = ""

    @property
    @abstractmethod
    def actor(self) -> Character:
        raise NotImplementedError

    @abstractmethod
    def affected(self) -> list[Character]:
        """Characters whose state this command may change."""
        raise NotImplementedError

    @abstractmethod
    def _perform(self) -> str:
        """Do the action; return the message describing it."""
        raise NotImplementedError

    @property
    def message(self) -> str:
        return self._message

    @property
    def health_changes(self) -> dict[Character, int]:
        """Health delta per affected character (negative = damage)."""
        return dict(self._health_changes)

    @property
    def executed(self) -> bool:
        return bool(self._snapshots)

    def execute(self) -> str:
        if self.executed:
            raise RuntimeError("Command was already executed")
        characters = list(dict.fromkeys(self.affected()))  # unique, order kept
        snapshots = [(character, character.save_state()) for character in characters]
        health_before = {character: character.health for character in characters}
        try:
            self._message = self._perform()
        except Exception:
            # An action that fails halfway must not leave the game half-changed.
            for character, memento in snapshots:
                character.restore_state(memento)
            raise
        self._snapshots = snapshots
        self._health_changes = {c: c.health - health_before[c] for c in characters}
        return self._message

    def undo(self) -> None:
        if not self.executed:
            raise RuntimeError("Nothing to undo: command was not executed")
        for character, memento in self._snapshots:
            character.restore_state(memento)
        self._snapshots = []


class AttackCommand(GameCommand):
    def __init__(self, attacker: Character, target: Character) -> None:
        super().__init__()
        self._attacker = attacker
        self._target = target

    @property
    def actor(self) -> Character:
        return self._attacker

    def affected(self) -> list[Character]:
        return [self._attacker, self._target]

    def _perform(self) -> str:
        dealt = self._target.take_damage(self._attacker.attack_power)
        return (
            f"{self._attacker.name} attacks {self._target.name} for {dealt} damage "
            f"(target HP: {self._target.health}/{self._target.max_health})."
        )


class HealCommand(GameCommand):
    def __init__(self, healer: Character, amount: int, target: Character | None = None) -> None:
        super().__init__()
        self._healer = healer
        self._amount = amount
        self._recipient = target or healer

    @property
    def actor(self) -> Character:
        return self._healer

    def affected(self) -> list[Character]:
        return [self._healer, self._recipient]

    def _perform(self) -> str:
        healed = self._recipient.heal(self._amount)
        return f"{self._healer.name} heals {self._recipient.name} for {healed} HP."


class UseAbilityCommand(GameCommand):
    def __init__(self, user: Character, ability_name: str, target: Character | None = None) -> None:
        super().__init__()
        self._user = user
        self._ability_name = ability_name
        self._target = target

    @property
    def actor(self) -> Character:
        return self._user

    def affected(self) -> list[Character]:
        return [self._user] + ([self._target] if self._target else [])

    def _perform(self) -> str:
        ability = self._user.get_ability(self._ability_name)
        return ability.use(self._user, self._target).message


class EquipCommand(GameCommand):
    def __init__(self, character: Character, item: Item) -> None:
        super().__init__()
        self._character = character
        self._item = item

    @property
    def actor(self) -> Character:
        return self._character

    def affected(self) -> list[Character]:
        return [self._character]

    def _perform(self) -> str:
        self._character.equip(self._item)
        return f"{self._character.name} equips {self._item.name}."
