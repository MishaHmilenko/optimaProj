"""CLIGraphic — console-specific building blocks: the console itself,
styled notices, tables, progress bars, meters and input dialogs.

Nothing here knows about characters or games; these are reusable
widgets for any text interface.
"""

from __future__ import annotations

import os
import sys
import textwrap
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Sequence, TypeVar

from .args import CommandError

T = TypeVar("T")


# -- console -----------------------------------------------------------------------


class IConsole(ABC):
    """Where text goes to and comes from. Swapped for a fake in tests or
    for a text widget in a future GUI window."""

    @abstractmethod
    def write(self, text: str = "") -> None: ...

    @abstractmethod
    def write_inline(self, text: str) -> None:
        """Rewrite the current line (progress bars)."""

    @abstractmethod
    def read(self, prompt: str = "") -> str:
        """Raises EOFError when input is exhausted."""

    @property
    def interactive(self) -> bool:
        return False


class StdConsole(IConsole):
    def __init__(self, color: bool | None = None) -> None:
        self._color = color

    @property
    def interactive(self) -> bool:
        return sys.stdout.isatty() and sys.stdin.isatty()

    @property
    def color(self) -> bool:
        if self._color is not None:
            return self._color
        return sys.stdout.isatty() and "NO_COLOR" not in os.environ

    def write(self, text: str = "") -> None:
        print(text)

    def write_inline(self, text: str) -> None:
        sys.stdout.write("\r" + text)
        sys.stdout.flush()

    def read(self, prompt: str = "") -> str:
        return input(prompt)


class BufferConsole(IConsole):
    """In-memory console: scripted answers in, captured lines out."""

    def __init__(self, answers: Sequence[str] = ()) -> None:
        self.lines: list[str] = []
        self._answers = list(answers)

    def feed(self, *answers: str) -> None:
        self._answers.extend(answers)

    @property
    def output(self) -> str:
        return "\n".join(self.lines)

    def write(self, text: str = "") -> None:
        self.lines.extend(str(text).split("\n"))

    def write_inline(self, text: str) -> None:
        pass

    def read(self, prompt: str = "") -> str:
        if not self._answers:
            raise EOFError
        answer = self._answers.pop(0)
        self.lines.append(f"{prompt}{answer}")
        return answer


# -- styles ------------------------------------------------------------------------


class Style:
    CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "cyan": "36"}

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        codes = ";".join(self.CODES[s] for s in styles)
        return f"\033[{codes}m{text}\033[0m"


class Level(Enum):
    INFO = ("·", ())
    SUCCESS = ("✓", ("green",))
    WARNING = ("!", ("yellow",))
    ERROR = ("✗", ("red", "bold"))

    @property
    def icon(self) -> str:
        return self.value[0]

    @property
    def styles(self) -> tuple[str, ...]:
        return self.value[1]


class Notice:
    def __init__(self, text: str, level: Level = Level.INFO) -> None:
        self.text = text
        self.level = level

    def format(self, style: Style) -> str:
        return style(f"{self.level.icon} {self.text}", *self.level.styles)


# -- widgets -----------------------------------------------------------------------


class Table:
    def __init__(self, headers: Sequence[str], rows: Sequence[Sequence[object]], max_width: int = 48) -> None:
        self.headers = [str(h) for h in headers]
        self.rows = [[self._cell(v, max_width) for v in row] for row in rows]

    @staticmethod
    def _cell(value: object, max_width: int) -> str:
        text = "" if value is None else str(value)
        return text if len(text) <= max_width else text[: max_width - 1] + "…"

    def format(self, style: Style, indent: str = "  ") -> list[str]:
        if not self.rows:
            return [indent + style("(empty)", "dim")]
        widths = [len(h) for h in self.headers]
        for row in self.rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def line(cells: Sequence[str]) -> str:
            return indent + " │ ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()

        rule = indent + "─┼─".join("─" * w for w in widths)
        return [style(line(self.headers), "bold"), rule, *(line(row) for row in self.rows)]


class Meter:
    def __init__(self, current: int, maximum: int, width: int = 20) -> None:
        self.current = max(0, current)
        self.maximum = max(1, maximum)
        self.width = width

    def format(self, style: Style) -> str:
        filled = round(self.width * min(self.current, self.maximum) / self.maximum)
        ratio = self.current / self.maximum
        color = "green" if ratio > 0.5 else "yellow" if ratio > 0.2 else "red"
        bar = style("█" * filled, color) + style("░" * (self.width - filled), "dim")
        return f"{bar} {self.current}/{self.maximum}"


class ProgressBar:
    """Redraws one line on a terminal; in non-interactive output (pipes,
    tests) prints only the final state, so logs stay clean."""

    def __init__(self, console: IConsole, total: int, label: str = "", width: int = 24) -> None:
        self._console = console
        self.total = max(1, total)
        self.label = label
        self.width = width
        self.done = 0

    def _text(self) -> str:
        filled = round(self.width * self.done / self.total)
        return f"  [{'#' * filled}{'-' * (self.width - filled)}] {self.done}/{self.total} {self.label}"

    def advance(self, step: int = 1, label: str | None = None) -> None:
        self.done = min(self.total, self.done + step)
        if label is not None:
            self.label = label
        if self._console.interactive:
            self._console.write_inline(self._text().ljust(72))

    def finish(self, label: str | None = None) -> None:
        self.done = self.total
        if label is not None:
            self.label = label
        if self._console.interactive:
            self._console.write_inline(self._text().ljust(72) + "\n")
        else:
            self._console.write(self._text())


def wrap(text: str, indent: str = "  ", width: int = 78) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width, initial_indent=indent, subsequent_indent=indent) or [""])
    return lines


# -- dialogs ------------------------------------------------------------------------


class Dialog:
    """Asks questions with defaults and validation. Re-asks on invalid
    answers; gives up after `attempts` tries or when input ends."""

    def __init__(self, console: IConsole, attempts: int = 3) -> None:
        self._console = console
        self._attempts = attempts

    def _read(self, prompt: str) -> str:
        try:
            return self._console.read(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            raise CommandError("Input cancelled.") from None

    def ask(self, prompt: str, default: str | None = None,
            convert: Callable[[str], T] = str, validate: Callable[[T], str | None] | None = None) -> T:
        suffix = f" [{default}]" if default not in (None, "") else ""
        for _ in range(self._attempts):
            raw = self._read(f"  {prompt}{suffix}: ") or (default or "")
            if raw == "" and default is None:
                self._console.write("    ! a value is required")
                continue
            try:
                value = convert(raw)
            except ValueError:
                self._console.write(f"    ! '{raw}' is not valid here")
                continue
            problem = validate(value) if validate else None
            if problem:
                self._console.write(f"    ! {problem}")
                continue
            return value
        raise CommandError(f"Too many invalid answers for '{prompt}'.")

    def ask_int(self, prompt: str, default: int | None = None, minimum: int | None = None,
                maximum: int | None = None) -> int:
        def check(value: int) -> str | None:
            if minimum is not None and value < minimum:
                return f"must be at least {minimum}"
            if maximum is not None and value > maximum:
                return f"must be at most {maximum}"
            return None

        return self.ask(prompt, None if default is None else str(default), int, check)

    def choose(self, prompt: str, options: Sequence[str], default: str | None = None) -> str:
        lowered = {o.lower(): o for o in options}

        def convert(raw: str) -> str:
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            if raw.lower() in lowered:
                return lowered[raw.lower()]
            raise ValueError(raw)

        for i, option in enumerate(options, start=1):
            self._console.write(f"    {i}) {option}")
        return self.ask(prompt, default, convert)

    def confirm(self, prompt: str, default: bool = False) -> bool:
        answer = self._read(f"  {prompt} [{'Y/n' if default else 'y/N'}]: ").lower()
        if not answer:
            return default
        return answer in ("y", "yes", "т", "так")
