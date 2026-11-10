"""CLI — the facade the rest of the program uses to talk to the console.

    cli.use_strategy(strategy)   register a category of commands
    cli.exec_command(raw)        parse with ArgsParser, find the command, run it
    cli.display(obj)             show an IRenderable / IDisplayable / str
    cli.success/info/warn/error  styled one-line notices
    cli.table / cli.progress     CLIGraphic widgets
    cli.dialog                   ask the user questions
    cli.push_mode / pop_mode     nested modes (e.g. the battle loop)

A *mode* (State pattern) is a named set of strategies with its own
prompt. The main mode holds the catalog strategies; starting a battle
pushes a "battle" mode whose strategy offers only battle actions;
`back` (or the end of the battle) pops it again. Built-in commands
(help, back, exit) are available in every mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from infra import IDisplayable, IDisplayer, IRenderable, RemoteServiceError

from .args import Args, ArgsParser, CommandError, UsageError
from .command import Command, FunctionCommand
from .console_renderer import ConsoleRenderer
from .graphic import Dialog, IConsole, Level, Notice, ProgressBar, StdConsole, Style, Table
from .strategy import ICommandStrategy, StaticStrategy


@dataclass
class Mode:
    name: str
    prompt: str = "> "
    strategies: list[ICommandStrategy] = field(default_factory=list)
    on_leave: Callable[[], None] | None = None


class CLI:
    def __init__(self, console: IConsole | None = None, parser: ArgsParser | None = None) -> None:
        self.console = console or StdConsole()
        self.style = Style(bool(getattr(self.console, "color", False)))
        self.renderer = ConsoleRenderer(self.console, self.style)
        self.dialog = Dialog(self.console)
        self._parser = parser or ArgsParser()
        self._modes: list[Mode] = [Mode("main")]
        self._running = False
        self._builtins = StaticStrategy("builtin", "General", self._builtin_commands())

    # -- strategies & modes ---------------------------------------------------------

    @property
    def mode(self) -> Mode:
        return self._modes[-1]

    def use_strategy(self, strategy: ICommandStrategy) -> "CLI":
        """Register a strategy's commands in the current mode."""
        known = self._command_table()
        for command in strategy.commands():
            for name in command.names:
                if name in known:
                    raise ValueError(f"Command '{name}' is already registered")
        self.mode.strategies.append(strategy)
        return self

    def remove_strategy(self, name: str) -> None:
        self.mode.strategies = [s for s in self.mode.strategies if s.name != name]

    def push_mode(self, mode: Mode) -> None:
        self._modes.append(mode)

    def pop_mode(self) -> Mode | None:
        if len(self._modes) == 1:
            return None
        mode = self._modes.pop()
        if mode.on_leave is not None:
            mode.on_leave()
        return mode

    def _strategies(self) -> list[ICommandStrategy]:
        return [self._builtins, *self.mode.strategies]

    def _command_table(self) -> dict[str, Command]:
        table: dict[str, Command] = {}
        for strategy in self._strategies():
            for command in strategy.commands():
                for name in command.names:
                    table[name] = command
        return table

    def find_command(self, name: str) -> Command | None:
        return self._command_table().get(name)

    # -- execution --------------------------------------------------------------------

    def parse(self, raw: str) -> Args:
        return self._parser.parse(raw)

    def exec_command(self, raw: str) -> bool:
        """Runs one line. Returns False if the command failed."""
        args = self.parse(raw)
        if not args.command:
            return True
        command = self.find_command(args.command)
        if command is None:
            self.error(f"Unknown command: '{args.command}'. Type 'help' to see available commands.")
            return False
        try:
            command.run(args, self)
        except UsageError as exc:
            self.error(f"{exc}")
            if "usage:" not in str(exc):
                self.info(f"usage: {command.signature}")
            return False
        except (CommandError, ValueError, KeyError, OSError, RemoteServiceError) as exc:
            message = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
            self.error(str(message))
            return False
        return True

    def run(self, banner: str = "") -> None:
        """Read-eval-print loop until `exit` or end of input."""
        if banner:
            self.display(banner)
        self.info("Type 'help' to list commands, 'exit' to quit.")
        self._running = True
        while self._running:
            try:
                line = self.console.read(self.mode.prompt)
            except (EOFError, KeyboardInterrupt):
                self.console.write()
                break
            self.exec_command(line)
        while self.pop_mode() is not None:
            pass

    def stop(self) -> None:
        self._running = False

    # -- output -------------------------------------------------------------------------

    def display(self, item: IRenderable | IDisplayable | str) -> None:
        if isinstance(item, IRenderable):
            item.render(self.renderer)
        elif isinstance(item, IDisplayable):
            self.console.write(item.to_display())
        else:
            self.console.write(str(item))

    def notify(self, text: str, level: Level = Level.INFO) -> None:
        self.console.write(Notice(text, level).format(self.style))

    def info(self, text: str) -> None:
        self.notify(text, Level.INFO)

    def success(self, text: str) -> None:
        self.notify(text, Level.SUCCESS)

    def warn(self, text: str) -> None:
        self.notify(text, Level.WARNING)

    def error(self, text: str) -> None:
        self.notify(text, Level.ERROR)

    def table(self, headers: list[str], rows: Iterable[Iterable[object]], max_width: int = 48) -> None:
        for line in Table(headers, [list(r) for r in rows], max_width).format(self.style):
            self.console.write(line)

    def progress(self, total: int, label: str = "") -> ProgressBar:
        return ProgressBar(self.console, total, label)

    def as_displayer(self) -> IDisplayer:
        """Adapter so core code that expects an IDisplayer (Game events)
        writes through this CLI."""
        return CliDisplayer(self)

    # -- built-in commands -----------------------------------------------------------------

    def _builtin_commands(self) -> list[Command]:
        return [
            FunctionCommand("help", self._help, "[command]", "list commands or describe one", aliases=("?",)),
            FunctionCommand("back", self._back, "", "leave the current mode"),
            FunctionCommand("exit", lambda a, c: self.stop(), "", "quit the program", aliases=("quit",)),
        ]

    def _help(self, args: Args, cli: "CLI") -> None:
        if args.positional:
            command = self.find_command(args.positional[0])
            if command is None:
                raise CommandError(f"No command named '{args.positional[0]}'.")
            self.display(self.style(command.signature, "bold"))
            self.display(f"  {command.description}")
            subs = getattr(command, "subcommands", None)
            if subs:
                self.table(["Sub-command", "Description"],
                           [[f"{command.name} {s.signature}", s.description] for s in subs], max_width=100)
            return
        self.display(self.style(f"Mode: {self.mode.name}", "bold"))
        for strategy in self._strategies():
            self.display(self.style(f"\n{strategy.title}", "cyan"))
            self.table(["Command", "Description"],
                       [[c.signature, c.description] for c in strategy.commands()], max_width=100)

    def _back(self, args: Args, cli: "CLI") -> None:
        if self.pop_mode() is None:
            self.info("Already in the main mode.")


class CliDisplayer(IDisplayer):
    def __init__(self, cli: CLI) -> None:
        self._cli = cli

    def display(self, item: IDisplayable) -> None:
        self._cli.display(item)
