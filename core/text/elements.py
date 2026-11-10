"""Class hierarchy for the structured-text system (plain-text variant).

VISITOR: every element has accept(visitor), which calls the visitor's
method for that element kind (see visitor.py).
ITERATOR: containers have walk(), a depth-first iterator over their
whole subtree (see iterators.py).

Each concrete element wraps a pure data model (core/text/models.py);
the element class only adds behaviour (render(), tree navigation).

PROTOTYPE: every element can clone() itself. A clone is a deep copy of
the element and its whole subtree, of the *same concrete class* - so an
HTML paragraph clones into an HTML paragraph without the caller knowing
which variant it holds. The clone is detached (no parent) and shares no
state with the original: models are copied, children are cloned.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace

from .iterators import DepthFirstIterator
from .models import HeadingData, ImageData, LinkData, ParagraphData
from .visitor import T, TextElementVisitor


class TextElement(ABC):
    """Root type for any node of the structured-text tree."""

    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def clone(self) -> "TextElement":
        """Prototype: return an independent deep copy of this element."""
        raise NotImplementedError

    @abstractmethod
    def accept(self, visitor: TextElementVisitor[T]) -> T:
        """Visitor: dispatch to the visit_* method for this element kind."""
        raise NotImplementedError

    def contents_entry(self) -> str | None:
        return None

    def __str__(self) -> str:
        return self.render()


class ContainerElement(TextElement, ABC):
    """Base class for elements that hold other elements as children."""

    def __init__(self) -> None:
        self._children: list[TextElement] = []
        self.parent: "ContainerElement | None" = None

    @property
    def children(self) -> tuple[TextElement, ...]:
        return tuple(self._children)

    def add(self, element: TextElement, index: int | None = None) -> None:
        if isinstance(element, ContainerElement):
            element.parent = self
        if index is None:
            self._children.append(element)
        else:
            self._children.insert(index, element)

    def remove(self, index: int) -> TextElement:
        return self._children.pop(index)

    def remove_element(self, element: TextElement) -> None:
        self._children.remove(element)

    def move(self, from_index: int, to_index: int) -> None:
        element = self._children.pop(from_index)
        self._children.insert(to_index, element)

    @abstractmethod
    def _clone_empty(self) -> "ContainerElement":
        """A copy of this container without children."""
        raise NotImplementedError

    def clone(self) -> "ContainerElement":
        copy = self._clone_empty()
        for child in self._children:
            copy.add(child.clone())
        return copy

    def walk(self, include_self: bool = False) -> DepthFirstIterator:
        """Iterator over every element below this container (pre-order)."""
        return DepthFirstIterator(self, include_start=include_self)

    def _render_children(self) -> str:
        return "\n\n".join(child.render() for child in self._children)

    def __len__(self) -> int:
        return len(self._children)

    def __iter__(self):
        return iter(self._children)


class LeafElement(TextElement, ABC):
    """Base class for elements with no children. Every leaf is built
    from exactly one data model, which is what makes cloning generic."""

    def __init__(self, data) -> None:
        self.data = data

    def clone(self) -> "LeafElement":
        return type(self)(replace(self.data))


# -- concrete leaf elements (each wraps its *Data model) ---------------------


class Paragraph(LeafElement):
    data: ParagraphData

    def accept(self, visitor: TextElementVisitor[T]) -> T:
        return visitor.visit_paragraph(self)

    def render(self) -> str:
        return self.data.text


class Link(LeafElement):
    data: LinkData

    def accept(self, visitor: TextElementVisitor[T]) -> T:
        return visitor.visit_link(self)

    def render(self) -> str:
        return f"{self.data.label} ({self.data.url})"


class Image(LeafElement):
    data: ImageData

    def accept(self, visitor: TextElementVisitor[T]) -> T:
        return visitor.visit_image(self)

    def render(self) -> str:
        return f"[image: {self.data.alt_text} -> {self.data.source}]"


# -- concrete container elements ---------------------------------------------


class Heading(ContainerElement):
    """A section heading. Also a container: paragraphs, links, images
    and nested headings can live under it."""

    def __init__(self, data: HeadingData) -> None:
        super().__init__()
        if data.level < 1:
            raise ValueError("Heading level must be a positive integer")
        self.data = data

    @property
    def title(self) -> str:
        return self.data.title

    @property
    def level(self) -> int:
        return self.data.level

    def _clone_empty(self) -> "Heading":
        return type(self)(replace(self.data))

    def accept(self, visitor: TextElementVisitor[T]) -> T:
        return visitor.visit_heading(self)

    def render(self) -> str:
        own_line = f"{'#' * self.level} {self.title}"
        if not self._children:
            return own_line
        return own_line + "\n\n" + self._render_children()

    def contents_entry(self) -> str:
        indent = "  " * (self.level - 1)
        return f"{indent}- {self.title}"


class Root(ContainerElement):
    """The top-level document container."""

    def _clone_empty(self) -> "Root":
        return type(self)()

    def accept(self, visitor: TextElementVisitor[T]) -> T:
        return visitor.visit_root(self)

    def render(self) -> str:
        return self._render_children()

    def table_of_contents(self) -> str:
        entries = (element.contents_entry() for element, _ in self.walk())
        return "\n".join(entry for entry in entries if entry is not None)
