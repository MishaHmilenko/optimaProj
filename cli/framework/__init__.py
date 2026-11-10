"""Reusable command-line framework (knows nothing about characters):
CLI facade, Args/ArgsParser, Command, ICommandStrategy, ConsoleRenderer
and the CLIGraphic widgets."""

from .args import Args, ArgsParser, CommandError, UsageError
from .command import Command, CommandGroup, FunctionCommand
from .strategy import ICommandStrategy, StaticStrategy
from .graphic import BufferConsole, Dialog, IConsole, Level, Meter, Notice, ProgressBar, StdConsole, Style, Table
from .console_renderer import ConsoleRenderer
from .cli import CLI, CliDisplayer, Mode

__all__ = [
    "Args", "ArgsParser", "CommandError", "UsageError",
    "Command", "CommandGroup", "FunctionCommand",
    "ICommandStrategy", "StaticStrategy",
    "BufferConsole", "Dialog", "IConsole", "Level", "Meter", "Notice", "ProgressBar", "StdConsole", "Style", "Table",
    "ConsoleRenderer",
    "CLI", "CliDisplayer", "Mode",
]
