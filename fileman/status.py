"""Status bar: the place for one-line feedback ("Saved", errors...).

Implements the IDisplayer interface from the infra layer of the earlier
practicals, so anything that already reports through an IDisplayer can
report into the status bar unchanged. Messages last until the next key.
"""

from __future__ import annotations

from infra import IDisplayable, IDisplayer, Message


class StatusBar(IDisplayer):
    def __init__(self) -> None:
        self.text = ""
        self.is_error = False

    def display(self, item: IDisplayable) -> None:
        self.text = item.to_display()
        self.is_error = False

    def info(self, text: str) -> None:
        self.display(Message(text))

    def error(self, text: str) -> None:
        self.text = text
        self.is_error = True

    def clear(self) -> None:
        self.text = ""
        self.is_error = False
