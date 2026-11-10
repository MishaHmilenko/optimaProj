"""Short-lived dialog states: a one-line text prompt and a choice.

Both draw the mode they were opened from underneath themselves (so the
directory listing or the file stays visible) and only replace the footer.
When finished they switch back to that mode, then run the callback - so
a callback is free to switch somewhere else again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from ..canvas import Canvas, Style
from ..keys import Key
from .base import Mode

if TYPE_CHECKING:
    from ..app import FileManagerApp


class PromptMode(Mode):
    name = "prompt"

    def __init__(
        self,
        app: "FileManagerApp",
        background: Mode,
        label: str,
        on_submit: Callable[[str], None],
        initial: str = "",
    ) -> None:
        self.background = background
        self.label = label
        self.on_submit = on_submit
        self.value = initial
        super().__init__(app)

    def bind_keys(self) -> None:
        self.bind("enter", self.submit, "confirm")
        self.bind("escape ctrl+c", self.cancel, "cancel")
        self.bind("backspace", self.erase, "delete last character")

    def on_unbound_key(self, key: Key) -> None:
        if key.is_printable:
            self.value += key.char

    def erase(self) -> None:
        self.value = self.value[:-1]

    def submit(self) -> None:
        self.app.switch(self.background)
        if self.value.strip():
            self.on_submit(self.value.strip())

    def cancel(self) -> None:
        self.app.switch(self.background)

    def render(self, canvas: Canvas) -> None:
        self.background.render(canvas)
        self.render_footer(canvas)

    def render_body(self, canvas: Canvas) -> None:  # the background draws the body
        pass

    def render_footer(self, canvas: Canvas) -> None:
        canvas.clear_row(canvas.status_row)
        canvas.write(canvas.status_row, " " + self.label, Style.PROMPT)
        canvas.write(canvas.status_row, self.value)
        canvas.cursor = (canvas.status_row, min(1 + len(self.label) + len(self.value), canvas.width - 1))
        canvas.clear_row(canvas.hints_row, fill=Style.FOOTER)
        for key, label in (("Enter", "OK"), ("Esc", "Cancel")):
            canvas.write(canvas.hints_row, f" {key} ", Style.KEY)
            canvas.write(canvas.hints_row, f" {label}  ", Style.FOOTER)


class ConfirmMode(Mode):
    """A question with single-key answers, e.g. "Save changes? y/n/Esc"."""

    name = "confirm"

    def __init__(
        self,
        app: "FileManagerApp",
        background: Mode,
        question: str,
        choices: dict[str, tuple[str, Callable[[], None]]],
    ) -> None:
        self.background = background
        self.question = question
        self.choices = choices  # key name -> (label, action)
        super().__init__(app)

    def bind_keys(self) -> None:
        for key_name, (label, action) in self.choices.items():
            self.bind(key_name, lambda action=action: self._choose(action), label)
        self.bind("escape ctrl+c", lambda: self.app.switch(self.background), "cancel")

    def _choose(self, action: Callable[[], None]) -> None:
        self.app.switch(self.background)
        action()

    def render(self, canvas: Canvas) -> None:
        self.background.render(canvas)
        self.render_footer(canvas)

    def render_body(self, canvas: Canvas) -> None:
        pass

    def render_footer(self, canvas: Canvas) -> None:
        canvas.write_line(canvas.status_row, " " + self.question, Style.PROMPT)
        canvas.clear_row(canvas.hints_row, fill=Style.FOOTER)
        for key_name, (label, _) in list(self.choices.items()) + [("Esc", ("Cancel", None))]:
            canvas.write(canvas.hints_row, f" {key_name} ", Style.KEY)
            canvas.write(canvas.hints_row, f" {label}  ", Style.FOOTER)
