"""ICommandStrategy — a pluggable set of related commands.

The CLI facade is parametrised by strategies (`cli.use_strategy(...)`):
each one contributes a category of commands (output, transforming
actions, infrastructure, game...). Adding a new category means writing
a new strategy; the CLI itself does not change (Open/Closed).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from .command import Command


class ICommandStrategy(ABC):
    #: short unique id, used by remove_strategy()
    name: str = ""
    #: heading shown in `help`
    title: str = ""

    @abstractmethod
    def commands(self) -> Iterable[Command]:
        raise NotImplementedError


class StaticStrategy(ICommandStrategy):
    """A strategy assembled from ready command objects."""

    def __init__(self, name: str, title: str, commands: Iterable[Command]) -> None:
        self.name = name
        self.title = title
        self._commands = list(commands)

    def commands(self) -> Iterable[Command]:
        return list(self._commands)
