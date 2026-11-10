"""The console, isolated behind one small interface.

Everything that touches the real terminal - raw mode, the alternate
screen, reading key bytes, the window size - lives in AnsiTerminal. The
rest of the program only sees ITerminal, so tests drive the whole
application through ScriptedTerminal (in tests/) without a real console.
"""

from __future__ import annotations

import os
import select
import signal
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Iterator

from .keys import Key, KeyDecoder

ENTER_ALT_SCREEN = "\x1b[?1049h"
LEAVE_ALT_SCREEN = "\x1b[?1049l"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"


class ITerminal(ABC):
    @abstractmethod
    def size(self) -> tuple[int, int]:
        """(columns, rows) of the visible area."""
        raise NotImplementedError

    @abstractmethod
    def write(self, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_key(self) -> Key:
        """Blocks until a key is pressed (or the window is resized, which
        is reported as Key("resize"))."""
        raise NotImplementedError

    @contextmanager
    def session(self) -> Iterator[None]:
        """Prepares the terminal for a full-screen app and restores it
        afterwards. No-op by default."""
        yield


class AnsiTerminal(ITerminal):
    """POSIX terminal (Linux, macOS) driven with ANSI escape sequences."""

    def __init__(self, stdin=None, stdout=None) -> None:
        self._in = stdin or sys.stdin
        self._out = stdout or sys.stdout
        self._decoder = KeyDecoder()
        self._pending: list[Key] = []
        self._resized = False

    def size(self) -> tuple[int, int]:
        try:
            size = os.get_terminal_size(self._out.fileno())
            return size.columns, size.lines
        except OSError:
            return 80, 24

    def write(self, text: str) -> None:
        self._out.write(text)
        self._out.flush()

    @contextmanager
    def session(self) -> Iterator[None]:
        import termios
        import tty

        fd = self._in.fileno()
        saved = termios.tcgetattr(fd)
        previous_handler = signal.signal(signal.SIGWINCH, self._on_resize)
        try:
            tty.setraw(fd)  # no line buffering, no echo, ^C/^Z/^S arrive as keys
            self.write(ENTER_ALT_SCREEN + HIDE_CURSOR)
            yield
        finally:
            self.write(SHOW_CURSOR + LEAVE_ALT_SCREEN)
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
            signal.signal(signal.SIGWINCH, previous_handler)

    def _on_resize(self, signum, frame) -> None:
        self._resized = True

    def _read_available(self, fd: int) -> str:
        data = os.read(fd, 1024)
        # Finish a UTF-8 character or escape sequence split across reads.
        while select.select([fd], [], [], 0.01)[0]:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", errors="replace")

    def read_key(self) -> Key:
        fd = self._in.fileno()
        while not self._pending:
            if self._resized:
                self._resized = False
                return Key("resize")
            try:
                ready, _, _ = select.select([fd], [], [], 0.2)
            except InterruptedError:
                continue  # SIGWINCH interrupted the wait
            if ready:
                self._pending.extend(self._decoder.decode(self._read_available(fd)))
        return self._pending.pop(0)
