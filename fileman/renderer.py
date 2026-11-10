"""Turns a Canvas into ANSI escape sequences.

The only class that knows about cursor addressing and SGR colour codes.
A whole frame is built as one string and written in one call, which
avoids flicker. Styles map to codes in one table, so a different colour
theme is a different table.
"""

from __future__ import annotations

from .canvas import Canvas, Style
from .terminal import HIDE_CURSOR, SHOW_CURSOR, ITerminal

RESET = "\x1b[0m"

DEFAULT_THEME: dict[Style, str] = {
    Style.NORMAL: "0",
    Style.HEADER: "0;1;30;46",
    Style.FOOTER: "0;30;47",
    Style.SELECTED: "0;30;43",
    Style.DIRECTORY: "0;1;34",
    Style.MUTED: "0;2",
    Style.GUTTER: "0;36",
    Style.INFO: "0;32",
    Style.ERROR: "0;1;31",
    Style.PROMPT: "0;1;33",
    Style.KEY: "0;1;30;47",
}


def sgr(code: str) -> str:
    return f"\x1b[{code}m"


class AnsiRenderer:
    def __init__(self, terminal: ITerminal, theme: dict[Style, str] | None = None) -> None:
        self._terminal = terminal
        self._theme = theme or DEFAULT_THEME

    def to_ansi(self, canvas: Canvas) -> str:
        parts: list[str] = [HIDE_CURSOR]
        for index, row in enumerate(canvas.rows):
            parts.append(f"\x1b[{index + 1};1H")
            used = 0
            for segment in row.segments:
                parts.append(sgr(self._theme[segment.style]) + segment.text)
                used += len(segment.text)
            # Pad to the full width in the row's fill style (coloured bars).
            parts.append(sgr(self._theme[row.fill]) + " " * max(canvas.width - used, 0))
            parts.append(RESET)
        if canvas.cursor is not None:
            row, col = canvas.cursor
            parts.append(f"\x1b[{row + 1};{col + 1}H" + SHOW_CURSOR)
        return "".join(parts)

    def draw(self, canvas: Canvas) -> None:
        self._terminal.write(self.to_ansi(canvas))
