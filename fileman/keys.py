"""Keyboard input as objects.

A Key has a stable name ("up", "enter", "ctrl+s", "a", "ж"...) that the
modes use as a selector in their key maps, plus the typed character for
printable keys. KeyDecoder turns the raw bytes a terminal sends in raw
mode - single bytes, multi-byte UTF-8 characters and ANSI escape
sequences - into Keys. It does no I/O, so it is tested without a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass

ESC = "\x1b"


@dataclass(frozen=True)
class Key:
    name: str
    char: str = ""

    @property
    def is_printable(self) -> bool:
        return bool(self.char) and self.char.isprintable()

    @classmethod
    def printable(cls, char: str) -> "Key":
        # Space gets a readable name so it can be bound ("space"), but it
        # still carries its character, so the editor can type it.
        return cls("space" if char == " " else char, char)


# Escape sequences sent by common terminals (xterm, iTerm2, Terminal.app,
# VS Code, tmux). Several keys have more than one spelling.
ESCAPE_SEQUENCES: dict[str, str] = {
    "[A": "up", "[B": "down", "[C": "right", "[D": "left",
    "OA": "up", "OB": "down", "OC": "right", "OD": "left",
    "[H": "home", "[F": "end", "OH": "home", "OF": "end",
    "[1~": "home", "[4~": "end", "[7~": "home", "[8~": "end",
    "[2~": "insert", "[3~": "delete",
    "[5~": "pageup", "[6~": "pagedown",
}

CONTROL_BYTES: dict[str, str] = {
    "\r": "enter", "\n": "enter",
    "\t": "tab",
    "\x7f": "backspace", "\x08": "backspace",
}


def _control_key(char: str) -> Key:
    if char in CONTROL_BYTES:
        return Key(CONTROL_BYTES[char])
    code = ord(char)
    if 1 <= code <= 26:
        return Key(f"ctrl+{chr(code + 96)}")
    return Key(f"control-{code}")


class KeyDecoder:
    """Stateless decoder from one chunk of terminal input to Keys.

    The terminal reads everything available after a key press in one go,
    so a whole escape sequence arrives in one chunk; a lone ESC byte is
    the Escape key itself.
    """

    def decode(self, data: str) -> list[Key]:
        keys: list[Key] = []
        i = 0
        while i < len(data):
            char = data[i]
            if char == ESC:
                key, consumed = self._decode_escape(data, i)
                keys.append(key)
                i += consumed
            elif ord(char) < 32 or char == "\x7f":
                keys.append(_control_key(char))
                i += 1
            else:
                keys.append(Key.printable(char))
                i += 1
        return keys

    def _decode_escape(self, data: str, start: int) -> tuple[Key, int]:
        rest = data[start + 1:]
        if not rest:
            return Key("escape"), 1
        # Longest known sequence that the input starts with.
        for length in (3, 2):
            sequence = rest[:length]
            if sequence in ESCAPE_SEQUENCES:
                return Key(ESCAPE_SEQUENCES[sequence]), 1 + length
        if rest[0] in "[O":
            # Unknown CSI/SS3 sequence: skip it up to its final byte so its
            # tail isn't typed into the editor as text.
            end = 1
            while end < len(rest) and not ("@" <= rest[end] <= "~"):
                end += 1
            return Key("unknown"), 1 + min(end + 1, len(rest))
        return Key("escape"), 1
