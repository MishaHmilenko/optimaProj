"""ViewerMode: read-only, scrollable view of a file (or of any text,
such as the help screen)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from ..canvas import Canvas, Style, clip
from ..viewport import Viewport
from .base import Mode

if TYPE_CHECKING:
    from ..app import FileManagerApp


class ViewerMode(Mode):
    name = "view"

    def __init__(
        self,
        app: "FileManagerApp",
        title: str,
        lines: list[str],
        path: str | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.document_title = title
        self.lines = lines or [""]
        self.path = path  # None for virtual documents (help): not editable
        self.on_close = on_close or app.back_to_browser
        self.viewport = Viewport()
        self._height = 10
        super().__init__(app)

    def bind_keys(self) -> None:
        self.bind("up k", lambda: self.scroll(-1), "scroll up")
        self.bind("down j", lambda: self.scroll(1), "scroll down")
        self.bind("pageup b", lambda: self.scroll(-self._height), "page up")
        self.bind("pagedown space", lambda: self.scroll(self._height), "page down")
        self.bind("home g", lambda: self.scroll(-len(self.lines)), "go to start")
        self.bind("end G", lambda: self.scroll(len(self.lines)), "go to end")
        self.bind("e", self.edit, "edit this file")
        self.bind("escape q backspace left", lambda: self.on_close(), "close")
        self.bind("?", self.app.show_help, "help")
        self.bind("ctrl+q ctrl+c", self.app.quit, "quit")

    def scroll(self, delta: int) -> None:
        self.viewport.scroll(delta, len(self.lines), self._height)

    def edit(self) -> None:
        if self.path is None:
            self.app.status.error("This document can't be edited")
        else:
            self.app.open_editor(self.path)

    def title(self) -> str:
        return "VIEW" if self.path else "HELP"

    def location(self) -> str:
        return self.document_title

    def render_body(self, canvas: Canvas) -> None:
        self._height = canvas.body_height
        self.viewport.scroll(0, len(self.lines), self._height)  # re-clamp after resize
        gutter = len(str(len(self.lines))) + 1
        for offset in range(canvas.body_height):
            screen_row = canvas.body_top + offset
            index = self.viewport.top + offset
            canvas.clear_row(screen_row)
            if index >= len(self.lines):
                canvas.write(screen_row, "~", Style.MUTED)
                continue
            canvas.write(screen_row, f"{index + 1:>{gutter}} ", Style.GUTTER)
            text = self.lines[index].replace("\t", "    ")
            canvas.write(screen_row, clip(text, canvas.width - gutter - 1))

    def position_text(self) -> str:
        last = min(self.viewport.top + self._height, len(self.lines))
        percent = 100 if len(self.lines) <= self._height else round(last * 100 / len(self.lines))
        return f"lines {self.viewport.top + 1}-{last} of {len(self.lines)} ({percent}%)"

    def render_footer(self, canvas: Canvas) -> None:
        super().render_footer(canvas)
        if not self.app.status.text:
            canvas.write(canvas.status_row, " " + self.position_text(), Style.MUTED)

    def hints(self) -> list[tuple[str, str]]:
        hints = [("↑↓", "Scroll"), ("PgUp/Dn", "Page")]
        if self.path:
            hints.append(("e", "Edit"))
        return hints + [("Esc", "Back"), ("?", "Help")]
