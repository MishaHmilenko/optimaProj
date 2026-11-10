"""ITERATOR over the text tree.

Several places needed "every element of the document, in reading order":
the table of contents, assigning ids in the CLI navigator, searching by
id. Each one had its own recursive function. DepthFirstIterator gives
that traversal once, through Python's iterator protocol, so callers just
write `for element, depth in root.walk():`.

It is lazy (the tree is expanded as you go, nothing is pre-collected),
uses an explicit stack instead of recursion, and the client never needs
to know that headings keep their children in a private list.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .elements import ContainerElement, TextElement


class DepthFirstIterator(Iterator[tuple["TextElement", int]]):
    """Yields (element, depth) pairs in pre-order: a heading comes right
    before its own content. Children of the start container have depth 1;
    with include_start=True the container itself comes first at depth 0."""

    def __init__(self, start: "ContainerElement", include_start: bool = False) -> None:
        self._stack: list[tuple["TextElement", int]] = []
        if include_start:
            self._stack.append((start, 0))
        else:
            self._push_children(start, 1)

    def _push_children(self, container: "ContainerElement", depth: int) -> None:
        # Reversed, so the first child is popped (visited) first.
        self._stack.extend((child, depth) for child in reversed(container.children))

    def __iter__(self) -> "DepthFirstIterator":
        return self

    def __next__(self) -> tuple["TextElement", int]:
        from .elements import ContainerElement

        if not self._stack:
            raise StopIteration
        element, depth = self._stack.pop()
        if isinstance(element, ContainerElement):
            self._push_children(element, depth + 1)
        return element, depth
