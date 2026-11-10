"""Infrastructure layer: decouples the Core systems from *how* output
is shown. Core code never calls print()/open() itself - it hands an
IDisplayable to whatever IDisplayer it was configured with.

IDisplayable - anything that knows how to describe itself as text.
IDisplayer   - anything that knows how to show an IDisplayable somewhere.

This mirrors the lecture's two-interface example: Game depends only on
IDisplayer (an abstraction), not on Console.WriteLine/print directly,
so swapping ConsoleDisplayer for FileDisplayer (or a test double) needs
no change to Core at all (Dependency Inversion).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class IDisplayable(ABC):
    @abstractmethod
    def to_display(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class Message(IDisplayable):
    """The simplest IDisplayable: a ready-made line of text. Used for
    one-off event descriptions (AbilityResult, combat log lines, etc.)."""

    text: str

    def to_display(self) -> str:
        return self.text


class IDisplayer(ABC):
    @abstractmethod
    def display(self, item: IDisplayable) -> None:
        raise NotImplementedError


class ConsoleDisplayer(IDisplayer):
    """Writes to standard output - the normal, interactive case."""

    def display(self, item: IDisplayable) -> None:
        print(item.to_display())


class FileDisplayer(IDisplayer):
    """Appends to a text file instead of the console. Swapping this in
    for ConsoleDisplayer requires no change anywhere in Core."""

    def __init__(self, path: str) -> None:
        self._path = path

    def display(self, item: IDisplayable) -> None:
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(item.to_display() + "\n")


class SilentDisplayer(IDisplayer):
    """Discards everything - useful for tests or headless runs."""

    def display(self, item: IDisplayable) -> None:
        pass
