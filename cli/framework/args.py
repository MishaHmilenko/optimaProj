"""Args — the object form of one parsed command line, and ArgsParser,
which turns raw user input into it."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field


class CommandError(Exception):
    """A command could not be completed; the message is shown to the user."""


class UsageError(CommandError):
    """The command was called with wrong arguments; the CLI shows usage."""


@dataclass
class Args:
    command: str = ""
    positional: list[str] = field(default_factory=list)
    options: dict[str, str] = field(default_factory=dict)

    # -- positional arguments ---------------------------------------------------

    def __len__(self) -> int:
        return len(self.positional)

    def arg(self, index: int, default: str | None = None) -> str | None:
        return self.positional[index] if index < len(self.positional) else default

    def require(self, count: int) -> None:
        if len(self.positional) < count:
            raise UsageError(f"expected {count} argument(s), got {len(self.positional)}")

    def shift(self) -> "Args":
        """Args for a sub-command: `db show char x` -> command 'show', args [char, x]."""
        if not self.positional:
            return Args("", [], dict(self.options))
        return Args(self.positional[0], self.positional[1:], dict(self.options))

    # -- options -----------------------------------------------------------------

    def option(self, *names: str, default: str | None = None) -> str | None:
        for name in names:
            if name in self.options:
                return self.options[name]
        return default

    def has(self, *names: str) -> bool:
        return any(name in self.options for name in names)

    def int_option(self, *names: str, default: int) -> int:
        raw = self.option(*names)
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            raise UsageError(f"option --{names[0]} must be a number, got '{raw}'") from None

    def list_option(self, *names: str) -> list[str]:
        raw = self.option(*names) or ""
        return [part.strip() for part in raw.split(",") if part.strip()]


class ArgsParser:
    """`cmd a b --key value -k value --flag --key=value "quoted arg"`.

    An option followed by another option (or by nothing) is a flag with
    an empty value. Single-dash tokens that look like negative numbers
    stay positional."""

    def parse(self, raw: str) -> Args:
        try:
            tokens = shlex.split(raw)
        except ValueError:  # unbalanced quotes - fall back to plain split
            tokens = raw.split()
        if not tokens:
            return Args()

        command, *rest = tokens
        positional: list[str] = []
        options: dict[str, str] = {}
        i = 0
        while i < len(rest):
            token = rest[i]
            key = self._option_name(token)
            if key is None:
                positional.append(token)
                i += 1
                continue
            if "=" in key:
                key, value = key.split("=", 1)
                options[key] = value
                i += 1
                continue
            following = rest[i + 1] if i + 1 < len(rest) else None
            if following is None or self._option_name(following) is not None:
                options[key] = ""
                i += 1
            else:
                options[key] = following
                i += 2
        return Args(command, positional, options)

    @staticmethod
    def _option_name(token: str) -> str | None:
        if token.startswith("--") and len(token) > 2:
            return token[2:]
        if token.startswith("-") and len(token) == 2 and not token[1].isdigit():
            return token[1:]
        return None
