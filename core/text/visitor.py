"""VISITOR for the text tree.

Some operations need different code for every kind of element but don't
belong inside the element classes: turning a document into JSON, or
rebuilding it in another format. Before, they were written as chains of
`if isinstance(element, Heading) ... elif isinstance(element, Paragraph)`.

With a visitor, each element's accept() calls the matching visit_* method
(double dispatch), so an operation is one class with one method per
element kind. Adding an operation never touches the element classes, and
forgetting a kind is impossible - the abstract methods force all five.

Format variants (Markdown/HTML) are subclasses of the plain elements and
inherit their accept(), so visitors treat them by their role.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from .elements import Heading, Image, Link, Paragraph, Root

T = TypeVar("T")


class TextElementVisitor(ABC, Generic[T]):
    @abstractmethod
    def visit_root(self, root: "Root") -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_heading(self, heading: "Heading") -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_paragraph(self, paragraph: "Paragraph") -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_link(self, link: "Link") -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_image(self, image: "Image") -> T:
        raise NotImplementedError
