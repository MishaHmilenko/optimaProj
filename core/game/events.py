"""OBSERVER: Game publishes events, any number of observers react.

Game used to call its displayer directly, so every new reaction to an
action (showing it, counting statistics, logging to a file...) would
have meant editing Game. Now Game is only the subject: it publishes a
GameEvent and doesn't know who is listening. Showing messages is one
observer (DisplayObserver), combat statistics are another
(CombatStatistics) - they are independent and added from outside.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infra import IDisplayer, IRenderable, IRenderer, Message

if TYPE_CHECKING:
    from .character import Character
    from .commands import GameCommand


@dataclass(frozen=True)
class GameEvent:
    """Base event: every event can be shown as one line of text."""

    message: str


@dataclass(frozen=True)
class ActionPerformed(GameEvent):
    command: "GameCommand"


@dataclass(frozen=True)
class ActionUndone(GameEvent):
    command: "GameCommand"


@dataclass(frozen=True)
class StatusReported(GameEvent):
    character: "Character"


class GameObserver(ABC):
    @abstractmethod
    def notify(self, event: GameEvent) -> None:
        raise NotImplementedError


class EventPublisher:
    """The subject side: keeps the subscriber list and fans events out."""

    def __init__(self) -> None:
        self._observers: list[GameObserver] = []

    def subscribe(self, observer: GameObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: GameObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def publish(self, event: GameEvent) -> None:
        for observer in list(self._observers):
            observer.notify(event)


class DisplayObserver(GameObserver):
    """Shows every event's message through an IDisplayer - exactly what
    Game used to do itself."""

    def __init__(self, displayer: IDisplayer) -> None:
        self._displayer = displayer

    def notify(self, event: GameEvent) -> None:
        self._displayer.display(Message(event.message))


class CombatStatistics(GameObserver, IRenderable):
    """Tallies damage and healing per character from the actions it
    observes, and takes them back out when an action is undone."""

    def __init__(self) -> None:
        self.damage_dealt: dict[str, int] = defaultdict(int)
        self.damage_taken: dict[str, int] = defaultdict(int)
        self.healing_done: dict[str, int] = defaultdict(int)
        self.actions: dict[str, int] = defaultdict(int)

    def notify(self, event: GameEvent) -> None:
        if isinstance(event, ActionPerformed):
            self._record(event.command, sign=1)
        elif isinstance(event, ActionUndone):
            self._record(event.command, sign=-1)

    def _record(self, command: "GameCommand", sign: int) -> None:
        actor = command.actor.name
        self.actions[actor] += sign
        for character, delta in command.health_changes.items():
            if delta < 0:
                self.damage_dealt[actor] += sign * -delta
                self.damage_taken[character.name] += sign * -delta
            elif delta > 0:
                self.healing_done[actor] += sign * delta

    def render(self, renderer: IRenderer) -> None:
        names = sorted(set(self.actions) | set(self.damage_taken))
        renderer.title("Combat statistics")
        if not names:
            renderer.text("No actions yet.")
            return
        renderer.table(
            ["Character", "Actions", "Dealt", "Taken", "Healed"],
            [[n, self.actions[n], self.damage_dealt[n], self.damage_taken[n], self.healing_done[n]] for n in names],
        )

    def report(self) -> str:
        names = sorted(set(self.actions) | set(self.damage_taken))
        if not names:
            return "No actions yet."
        return "\n".join(
            f"{name}: {self.actions[name]} actions, dealt {self.damage_dealt[name]}, "
            f"took {self.damage_taken[name]}, healed {self.healing_done[name]}"
            for name in names
        )
