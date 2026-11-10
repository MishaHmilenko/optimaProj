"""ConsoleRenderer — the CLI's implementation of the IRenderer interface
that the inner layers declared (infra.rendering). It turns abstract
"title / field / table / link" calls into text lines using CLIGraphic
widgets."""

from __future__ import annotations

from typing import Sequence

from infra.rendering import IRenderer

from .graphic import IConsole, Meter, Style, Table, wrap


class ConsoleRenderer(IRenderer):
    LABEL_WIDTH = 14

    def __init__(self, console: IConsole, style: Style) -> None:
        self._console = console
        self._style = style

    def title(self, text: str) -> None:
        self._console.write(self._style(text, "bold", "cyan"))

    def field(self, label: str, value: object) -> None:
        if value in (None, ""):
            return
        indent = " " * (self.LABEL_WIDTH + 3)
        lines = wrap(str(value), indent=indent, width=78)
        first = lines[0][len(indent):] if lines else ""
        self._console.write(f"  {self._style(label.ljust(self.LABEL_WIDTH), 'dim')} {first}")
        for line in lines[1:]:
            self._console.write(line)

    def text(self, text: str) -> None:
        if text:
            for line in wrap(text):
                self._console.write(line)

    def bullet_list(self, items: Sequence[str], label: str | None = None) -> None:
        if label:
            self._console.write(f"  {self._style(label, 'dim')}:")
        for item in items:
            self._console.write(f"    - {item}")

    def table(self, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
        for line in Table(headers, rows).format(self._style):
            self._console.write(line)

    def link(self, label: str, url: str) -> None:
        self._console.write(f"  {self._style(('↗ ' + label).ljust(self.LABEL_WIDTH), 'dim')} {url}")

    def meter(self, label: str, current: int, maximum: int) -> None:
        self._console.write(f"  {self._style(label.ljust(self.LABEL_WIDTH), 'dim')} "
                            f"{Meter(current, maximum).format(self._style)}")

    def separator(self) -> None:
        self._console.write(self._style("  " + "─" * 40, "dim"))
