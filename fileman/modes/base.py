"""Base class of every state of the application (STATE pattern).

FileManagerApp (the context) holds one current Mode and forwards every
key to it; a mode reacts and, when the user moves to another part of the
program, tells the app to switch to a different mode. The same key can
therefore mean different things: Enter opens a directory in the browser,
does nothing special in the viewer and splits a line in the editor.

Key handling reuses the CLI framework's Command objects: a mode's key
map is a dict from key names ("up", "ctrl+s", "e") to FunctionCommand.
Binding a new key is one bind() call, and the commands' descriptions
feed the help screen.

Drawing is a TEMPLATE METHOD: render() always draws header, body and
footer in that order; subclasses fill in the body and may tweak the
header title, the location and the key hints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from cli.framework import Args, Command, FunctionCommand

from ..canvas import Canvas, Style, clip
from ..keys import Key

if TYPE_CHECKING:
    from ..app import FileManagerApp


class Mode(ABC):
    name: str = "mode"

    def __init__(self, app: "FileManagerApp") -> None:
        self.app = app
        self.keys: dict[str, Command] = {}
        self.bind_keys()

    # -- keys ------------------------------------------------------------------------------

    @abstractmethod
    def bind_keys(self) -> None:
        """Register this mode's key handlers in self.keys."""
        raise NotImplementedError

    def bind(self, key_names: str, action, description: str = "") -> None:
        """Bind one action to one or more keys ("q escape")."""
        for index, key_name in enumerate(key_names.split()):
            # Only the first spelling is described, to keep help short.
            self.keys[key_name] = FunctionCommand(key_name, lambda _args, _cli, action=action: action(),
                                                  description=description if index == 0 else "")

    def handle_key(self, key: Key) -> None:
        command = self.keys.get(key.name)
        if command is not None:
            command.execute(Args(key.name), None)
        else:
            self.on_unbound_key(key)

    def on_unbound_key(self, key: Key) -> None:
        """Keys without a binding are ignored by default; the editor
        overrides this to type characters."""

    def on_enter(self) -> None:
        """Called each time the app switches to this mode."""

    def help_lines(self) -> list[str]:
        return [f"  {name:<10} {c.description}" for name, c in self.keys.items() if c.description]

    # -- drawing (template method) ------------------------------------------------------------

    def render(self, canvas: Canvas) -> None:
        self.render_header(canvas)
        self.render_body(canvas)
        self.render_footer(canvas)

    def title(self) -> str:
        return self.name.upper()

    def location(self) -> str:
        return ""

    def render_header(self, canvas: Canvas) -> None:
        left = f" FileMan  {self.title()} "
        location = clip(self.location(), canvas.width - len(left) - 2)
        canvas.write_line(canvas.header_row, f"{left} {location}", Style.HEADER)

    @abstractmethod
    def render_body(self, canvas: Canvas) -> None:
        raise NotImplementedError

    def hints(self) -> list[tuple[str, str]]:
        """(key, label) pairs shown in the bottom bar."""
        return []

    def render_footer(self, canvas: Canvas) -> None:
        status = self.app.status
        canvas.clear_row(canvas.status_row)
        if status.text:
            canvas.write(canvas.status_row, " " + status.text, Style.ERROR if status.is_error else Style.INFO)
        canvas.clear_row(canvas.hints_row, fill=Style.FOOTER)
        for key, label in self.hints():
            canvas.write(canvas.hints_row, f" {key} ", Style.KEY)
            canvas.write(canvas.hints_row, f" {label}  ", Style.FOOTER)
