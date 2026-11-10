"""Scrolling arithmetic shared by every mode.

The browser's selection, the viewer's top line and the editor's cursor
all need the same thing: keep a position inside [0, count) and keep it
visible in a window of `height` rows. Extracted once instead of three
times.
"""

from __future__ import annotations


class Viewport:
    def __init__(self) -> None:
        self.top = 0

    @staticmethod
    def clamp(value: int, count: int) -> int:
        return max(0, min(value, count - 1)) if count > 0 else 0

    def follow(self, position: int, height: int) -> None:
        """Scroll just enough for `position` to be visible."""
        if position < self.top:
            self.top = position
        elif position >= self.top + height:
            self.top = position - height + 1
        self.top = max(self.top, 0)

    def scroll(self, delta: int, count: int, height: int) -> None:
        """Scroll the window itself (viewer), never past the content."""
        self.top = max(0, min(self.top + delta, max(count - height, 0)))
