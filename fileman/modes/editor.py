"""EditorMode: edits a file in a TextBuffer and saves it back.

On top of the viewer's controls it captures typed characters. Leaving
with unsaved changes goes through a ConfirmMode (save / discard /
cancel) instead of silently losing work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..buffer import TextBuffer
from ..canvas import Canvas, Style
from ..keys import Key
from ..viewport import Viewport
from .base import Mode
from .prompt import ConfirmMode

if TYPE_CHECKING:
    from ..app import FileManagerApp


class EditorMode(Mode):
    name = "edit"

    def __init__(self, app: "FileManagerApp", path: str, text: str) -> None:
        self.path = path
        self.buffer = TextBuffer(text)
        self.viewport = Viewport()
        self.left = 0  # horizontal scroll
        self._height = 10
        super().__init__(app)

    def bind_keys(self) -> None:
        b = self.buffer
        self.bind("up", b.move_up, "cursor up")
        self.bind("down", b.move_down, "cursor down")
        self.bind("left", b.move_left, "cursor left")
        self.bind("right", b.move_right, "cursor right")
        self.bind("home", b.move_home, "start of line")
        self.bind("end", b.move_end, "end of line")
        self.bind("pageup", lambda: b.move_up(self._height), "page up")
        self.bind("pagedown", lambda: b.move_down(self._height), "page down")
        self.bind("enter", b.newline, "new line")
        self.bind("backspace", b.backspace, "delete before cursor")
        self.bind("delete", b.delete, "delete under cursor")
        self.bind("tab", b.insert_tab, "insert 4 spaces")
        self.bind("ctrl+s", self.save, "save")
        self.bind("ctrl+z", self.undo, "undo")
        self.bind("escape", self.leave, "close the editor")
        self.bind("ctrl+q", self.quit, "quit the app")

    def on_unbound_key(self, key: Key) -> None:
        if key.is_printable:
            self.buffer.insert(key.char)

    # -- actions ----------------------------------------------------------------------------

    def save(self) -> None:
        self.app.fs.write_text(self.path, self.buffer.text)
        self.buffer.mark_saved()
        self.app.status.info(f"Saved {self.path}")

    def undo(self) -> None:
        if not self.buffer.undo():
            self.app.status.info("Nothing to undo")

    def _close(self) -> None:
        self.app.open_viewer(self.path)

    def _confirm_unsaved(self, then) -> None:
        def save_then() -> None:
            self.save()
            then()

        self.app.switch(ConfirmMode(self.app, self, "Save changes before leaving?", {
            "y": ("Save", save_then),
            "n": ("Discard", then),
        }))

    def leave(self) -> None:
        if self.buffer.modified:
            self._confirm_unsaved(self._close)
        else:
            self._close()

    def quit(self) -> None:
        if self.buffer.modified:
            self._confirm_unsaved(self.app.quit)
        else:
            self.app.quit()

    # -- drawing ----------------------------------------------------------------------------

    def title(self) -> str:
        return "EDIT" + (" *" if self.buffer.modified else "")

    def location(self) -> str:
        return self.path

    def render_body(self, canvas: Canvas) -> None:
        self._height = canvas.body_height
        b = self.buffer
        gutter = len(str(len(b.lines))) + 1
        text_width = canvas.width - gutter - 1
        self.viewport.follow(b.row, canvas.body_height)
        if b.col < self.left:
            self.left = b.col
        elif b.col >= self.left + text_width:
            self.left = b.col - text_width + 1

        for offset in range(canvas.body_height):
            screen_row = canvas.body_top + offset
            index = self.viewport.top + offset
            canvas.clear_row(screen_row)
            if index >= len(b.lines):
                canvas.write(screen_row, "~", Style.MUTED)
                continue
            canvas.write(screen_row, f"{index + 1:>{gutter}} ", Style.GUTTER)
            canvas.write(screen_row, b.lines[index][self.left:self.left + text_width])

        canvas.cursor = (canvas.body_top + b.row - self.viewport.top, gutter + 1 + b.col - self.left)

    def render_footer(self, canvas: Canvas) -> None:
        super().render_footer(canvas)
        if not self.app.status.text:
            state = "modified" if self.buffer.modified else "saved"
            canvas.write(canvas.status_row, f" Ln {self.buffer.row + 1}, Col {self.buffer.col + 1} · {state}",
                         Style.MUTED)

    def hints(self) -> list[tuple[str, str]]:
        return [("^S", "Save"), ("^Z", "Undo"), ("Esc", "Close"), ("^Q", "Quit")]
