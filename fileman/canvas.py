"""The virtual screen.

Canvas is an in-memory picture of one frame: rows of styled text
segments split into three regions - a header row, the body, and a
two-row footer (status line + key hints). Modes draw on a Canvas and
never write escape codes themselves; turning a Canvas into terminal
output is AnsiRenderer's job. Because a Canvas is plain data, tests
assert on what is on screen through canvas.text(row).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Style(Enum):
    NORMAL = "normal"
    HEADER = "header"
    FOOTER = "footer"
    SELECTED = "selected"
    DIRECTORY = "directory"
    MUTED = "muted"
    GUTTER = "gutter"
    INFO = "info"
    ERROR = "error"
    PROMPT = "prompt"
    KEY = "key"


@dataclass
class Segment:
    text: str
    style: Style = Style.NORMAL


@dataclass
class Row:
    segments: list[Segment] = field(default_factory=list)
    fill: Style = Style.NORMAL

    @property
    def text(self) -> str:
        return "".join(segment.text for segment in self.segments)


class Canvas:
    HEADER_ROWS = 1
    FOOTER_ROWS = 2

    def __init__(self, width: int, height: int) -> None:
        self.width = max(width, 20)
        self.height = max(height, self.HEADER_ROWS + self.FOOTER_ROWS + 3)
        self.rows = [Row() for _ in range(self.height)]
        self.cursor: tuple[int, int] | None = None  # (row, col) to show the text cursor

    # -- regions --------------------------------------------------------------------

    @property
    def body_top(self) -> int:
        return self.HEADER_ROWS

    @property
    def body_height(self) -> int:
        return self.height - self.HEADER_ROWS - self.FOOTER_ROWS

    @property
    def header_row(self) -> int:
        return 0

    @property
    def status_row(self) -> int:
        return self.height - 2

    @property
    def hints_row(self) -> int:
        return self.height - 1

    # -- drawing --------------------------------------------------------------------------

    def clear_row(self, row: int, fill: Style = Style.NORMAL) -> None:
        self.rows[row] = Row(fill=fill)

    def write(self, row: int, text: str, style: Style = Style.NORMAL) -> None:
        """Appends text to a row, clipped to the canvas width."""
        line = self.rows[row]
        room = self.width - len(line.text)
        if room > 0 and text:
            line.segments.append(Segment(text[:room], style))

    def write_line(self, row: int, text: str, style: Style = Style.NORMAL) -> None:
        """Replaces a row with one segment and fills the rest with its style."""
        self.clear_row(row, fill=style)
        self.write(row, text, style)

    def text(self, row: int) -> str:
        return self.rows[row].text

    def body_text(self) -> list[str]:
        return [self.text(r) for r in range(self.body_top, self.body_top + self.body_height)]

    def dump(self) -> str:
        """Whole screen as plain text - handy in tests and for debugging."""
        return "\n".join(row.text.rstrip() for row in self.rows)


def clip(text: str, width: int) -> str:
    """Shortens text to width, marking the cut with an ellipsis."""
    if width <= 0:
        return ""
    return text if len(text) <= width else text[: width - 1] + "…"
