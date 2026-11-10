"""The editor's document: lines of text plus a cursor.

TextBuffer is pure logic (no terminal, no files), so every editing
operation is unit-tested directly.

Undo reuses the MEMENTO idea from the game module: before each change
the buffer saves an opaque BufferMemento of its own state. Consecutive
typed characters on one line are grouped into a single undo step, the
way real editors behave - otherwise undoing a word would take one
Ctrl+Z per letter.
"""

from __future__ import annotations

from dataclasses import dataclass

TAB = "    "


@dataclass(frozen=True)
class BufferMemento:
    """Snapshot of a buffer. Only TextBuffer reads its fields."""

    _lines: tuple[str, ...]
    _row: int
    _col: int


class TextBuffer:
    MAX_UNDO = 200

    def __init__(self, text: str = "") -> None:
        self.trailing_newline = text.endswith("\n")
        body = text[:-1] if self.trailing_newline else text
        self.lines: list[str] = body.split("\n") if body else [""]
        self.row = 0
        self.col = 0
        self._undo: list[BufferMemento] = []
        self._typing_on_row: int | None = None
        self._saved_state = self._snapshot()

    # -- state -------------------------------------------------------------------------------

    @property
    def text(self) -> str:
        return "\n".join(self.lines) + ("\n" if self.trailing_newline else "")

    @property
    def modified(self) -> bool:
        return self._snapshot()._lines != self._saved_state._lines

    def mark_saved(self) -> None:
        self._saved_state = self._snapshot()

    @property
    def line(self) -> str:
        return self.lines[self.row]

    # -- memento / undo ---------------------------------------------------------------------

    def _snapshot(self) -> BufferMemento:
        return BufferMemento(tuple(self.lines), self.row, self.col)

    def _restore(self, memento: BufferMemento) -> None:
        self.lines = list(memento._lines)
        self.row, self.col = memento._row, memento._col

    def _checkpoint(self, typing: bool = False) -> None:
        """Save a snapshot before a change, merging runs of typing."""
        if typing and self._typing_on_row == self.row:
            return
        self._undo.append(self._snapshot())
        del self._undo[:-self.MAX_UNDO]
        self._typing_on_row = self.row if typing else None

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._restore(self._undo.pop())
        self._typing_on_row = None
        return True

    # -- cursor movement -------------------------------------------------------------------------

    def _end_typing(self) -> None:
        self._typing_on_row = None

    def _clamp_col(self) -> None:
        self.col = min(self.col, len(self.line))

    def move_up(self, count: int = 1) -> None:
        self._end_typing()
        self.row = max(0, self.row - count)
        self._clamp_col()

    def move_down(self, count: int = 1) -> None:
        self._end_typing()
        self.row = min(len(self.lines) - 1, self.row + count)
        self._clamp_col()

    def move_left(self) -> None:
        self._end_typing()
        if self.col > 0:
            self.col -= 1
        elif self.row > 0:
            self.row -= 1
            self.col = len(self.line)

    def move_right(self) -> None:
        self._end_typing()
        if self.col < len(self.line):
            self.col += 1
        elif self.row < len(self.lines) - 1:
            self.row += 1
            self.col = 0

    def move_home(self) -> None:
        self._end_typing()
        self.col = 0

    def move_end(self) -> None:
        self._end_typing()
        self.col = len(self.line)

    # -- editing -----------------------------------------------------------------------------------

    def insert(self, text: str) -> None:
        if not text:
            return
        self._checkpoint(typing=True)
        self.lines[self.row] = self.line[: self.col] + text + self.line[self.col:]
        self.col += len(text)

    def insert_tab(self) -> None:
        self.insert(TAB)

    def newline(self) -> None:
        self._checkpoint()
        before, after = self.line[: self.col], self.line[self.col:]
        indent = before[: len(before) - len(before.lstrip(" "))]  # keep indentation
        self.lines[self.row] = before
        self.lines.insert(self.row + 1, indent + after)
        self.row += 1
        self.col = len(indent)

    def backspace(self) -> None:
        if self.col == 0 and self.row == 0:
            return
        self._checkpoint()
        if self.col > 0:
            self.lines[self.row] = self.line[: self.col - 1] + self.line[self.col:]
            self.col -= 1
        else:
            previous = self.lines[self.row - 1]
            self.lines[self.row - 1] = previous + self.line
            del self.lines[self.row]
            self.row -= 1
            self.col = len(previous)

    def delete(self) -> None:
        if self.col == len(self.line) and self.row == len(self.lines) - 1:
            return
        self._checkpoint()
        if self.col < len(self.line):
            self.lines[self.row] = self.line[: self.col] + self.line[self.col + 1:]
        else:
            self.lines[self.row] = self.line + self.lines[self.row + 1]
            del self.lines[self.row + 1]
