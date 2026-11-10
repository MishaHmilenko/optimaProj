"""Command — one user-visible command as an object (Command pattern),
instead of a bare lambda in a dictionary. It carries its own name,
usage line and description, validates its arguments and then runs.

CommandGroup is a Composite: a command made of sub-commands
(`db chars`, `game new`, ...), dispatched with the same mechanism.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Iterable

from .args import Args, UsageError

if TYPE_CHECKING:
    from .cli import CLI


class Command(ABC):
    name: str = ""
    usage: str = ""
    description: str = ""
    aliases: tuple[str, ...] = ()
    min_args: int = 0

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)

    @property
    def signature(self) -> str:
        return f"{self.name} {self.usage}".strip()

    def run(self, args: Args, cli: "CLI") -> None:
        """Template method: validate, then execute."""
        if len(args) < self.min_args:
            raise UsageError(f"'{self.name}' needs at least {self.min_args} argument(s)")
        self.execute(args, cli)

    @abstractmethod
    def execute(self, args: Args, cli: "CLI") -> None:
        raise NotImplementedError


class FunctionCommand(Command):
    """Adapter for simple commands that are just a function."""

    def __init__(self, name: str, handler: Callable[[Args, "CLI"], None], usage: str = "",
                 description: str = "", min_args: int = 0, aliases: tuple[str, ...] = ()) -> None:
        self.name = name
        self.usage = usage
        self.description = description
        self.min_args = min_args
        self.aliases = aliases
        self._handler = handler

    def execute(self, args: Args, cli: "CLI") -> None:
        self._handler(args, cli)


class CommandGroup(Command):
    """Composite: `<group> <sub-command> ...`."""

    def __init__(self, name: str, description: str, commands: Iterable[Command]) -> None:
        self.name = name
        self.description = description
        self._commands: dict[str, Command] = {}
        for command in commands:
            for alias in command.names:
                self._commands[alias] = command
        self.usage = "<" + "|".join(dict.fromkeys(c.name for c in self._commands.values())) + "> ..."

    @property
    def subcommands(self) -> list[Command]:
        return list(dict.fromkeys(self._commands.values()))

    def execute(self, args: Args, cli: "CLI") -> None:
        sub = args.shift()
        command = self._commands.get(sub.command)
        if command is None:
            if sub.command:
                cli.error(f"Unknown sub-command '{self.name} {sub.command}'.")
            cli.table(["Command", "Description"],
                      [[f"{self.name} {c.signature}", c.description] for c in self.subcommands], max_width=100)
            return
        try:
            command.run(sub, cli)
        except UsageError as exc:
            raise UsageError(f"{exc}\n  usage: {self.name} {command.signature}") from None
