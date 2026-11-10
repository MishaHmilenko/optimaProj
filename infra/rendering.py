"""Presentation contract between the inner layers and any user interface.

Inner classes (Character, Item, DTOs, statistics, battle results) know
*what* they consist of: a title, some fields, a list, a table, links.
They do not know *how* that is shown. So they implement IRenderable and
describe themselves through an abstract IRenderer.

The interface IRenderer is declared here, in the inner library, and is
implemented by the outer UI layer (cli.framework.ConsoleRenderer today,
a GUI renderer later). The dependency therefore points inwards
(Dependency Inversion): core/infra never import anything from cli.

This is the "IRenderable + aggregated IRenderer" variant from the
practical: one renderer object is passed into render(), Visitor-style.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence


class IRenderer(ABC):
    """Building blocks every user interface must be able to show."""

    @abstractmethod
    def title(self, text: str) -> None: ...

    @abstractmethod
    def field(self, label: str, value: object) -> None: ...

    @abstractmethod
    def text(self, text: str) -> None: ...

    @abstractmethod
    def bullet_list(self, items: Sequence[str], label: str | None = None) -> None: ...

    @abstractmethod
    def table(self, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> None: ...

    @abstractmethod
    def link(self, label: str, url: str) -> None: ...

    @abstractmethod
    def meter(self, label: str, current: int, maximum: int) -> None:
        """A bounded value, e.g. health 80/120."""

    @abstractmethod
    def separator(self) -> None: ...


class IRenderable(ABC):
    """Anything that can describe itself to an IRenderer."""

    @abstractmethod
    def render(self, renderer: IRenderer) -> None:
        raise NotImplementedError
