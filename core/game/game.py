"""Game: the MEDIATOR between characters (characters never act on each
other directly - every interaction goes through Game).

Since the behavioral-patterns refactor, Game also is:
  * the COMMAND invoker - actions are GameCommand objects it executes
    and keeps in a history, which makes undo() possible;
  * the OBSERVER subject - it publishes GameEvents instead of calling a
    displayer itself.

The public API (basic_attack, heal, use_ability, equip_item,
report_status and the Game(displayer) constructor) is unchanged, so
existing callers and tests keep working.
"""

from __future__ import annotations

from infra import ConsoleDisplayer, IDisplayer

from .character import Character
from .commands import AttackCommand, EquipCommand, GameCommand, HealCommand, UseAbilityCommand
from .events import (
    ActionPerformed,
    ActionUndone,
    DisplayObserver,
    EventPublisher,
    GameObserver,
    StatusReported,
)
from .items import Item


class Game:
    def __init__(self, displayer: IDisplayer | None = None) -> None:
        self._characters: list[Character] = []
        self._history: list[GameCommand] = []
        self._events = EventPublisher()
        self._events.subscribe(DisplayObserver(displayer or ConsoleDisplayer()))

    # -- observers ----------------------------------------------------------------

    def subscribe(self, observer: GameObserver) -> None:
        self._events.subscribe(observer)

    def unsubscribe(self, observer: GameObserver) -> None:
        self._events.unsubscribe(observer)

    # -- characters ---------------------------------------------------------------

    def add_character(self, character: Character) -> None:
        self._characters.append(character)

    @property
    def characters(self) -> tuple[Character, ...]:
        return tuple(self._characters)

    # -- commands -----------------------------------------------------------------

    def execute(self, command: GameCommand) -> None:
        """Runs a command, remembers it for undo and announces it. If the
        command fails, nothing is recorded or announced."""
        message = command.execute()
        self._history.append(command)
        self._events.publish(ActionPerformed(message, command))

    def undo(self) -> GameCommand | None:
        """Reverts the most recent action; returns it, or None if there
        is nothing to undo."""
        if not self._history:
            return None
        command = self._history.pop()
        command.undo()
        self._events.publish(ActionUndone(f"Undone: {command.message}", command))
        return command

    @property
    def history(self) -> tuple[GameCommand, ...]:
        return tuple(self._history)

    # -- the original API, now expressed as commands ---------------------------------

    def basic_attack(self, attacker: Character, target: Character) -> None:
        self.execute(AttackCommand(attacker, target))

    def heal(self, healer: Character, amount: int, target: Character | None = None) -> None:
        self.execute(HealCommand(healer, amount, target))

    def use_ability(self, user: Character, ability_name: str,
                     target: Character | None = None) -> None:
        self.execute(UseAbilityCommand(user, ability_name, target))

    def equip_item(self, character: Character, item: Item) -> None:
        self.execute(EquipCommand(character, item))

    def report_status(self) -> None:
        for character in self._characters:
            self._events.publish(StatusReported(str(character), character))
