"""PROTOTYPE registry and format conversion.

PrototypeRegistry keeps named, pre-configured elements (templates: a
disclaimer paragraph, a standard "Contacts" section with links...) and
hands out fresh clones of them. Creating a complex element this way
needs no knowledge of its concrete class or of how to assemble it, and
it doesn't require a dedicated factory per template either - the
alternative the practical warns about.

DocumentConverter re-creates an existing tree in another format: a
visitor that rebuilds every node through a TextElementFactory from
copies of the nodes' data models.
"""

from __future__ import annotations

from dataclasses import replace

from .elements import ContainerElement, Heading, Image, Link, Paragraph, Root, TextElement
from .families import TextElementFactory
from .visitor import TextElementVisitor


class PrototypeRegistry:
    def __init__(self) -> None:
        self._prototypes: dict[str, TextElement] = {}

    def register(self, name: str, element: TextElement) -> None:
        """Stores a private copy, so later edits to the element the
        caller passed in don't change the template."""
        self._prototypes[name] = element.clone()

    def unregister(self, name: str) -> None:
        self._prototypes.pop(name, None)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._prototypes))

    def create(self, name: str) -> TextElement:
        try:
            prototype = self._prototypes[name]
        except KeyError:
            raise ValueError(f"No template named '{name}'") from None
        return prototype.clone()


class DocumentConverter(TextElementVisitor[TextElement]):
    """Re-creates a document in another format. Implemented as a VISITOR:
    each visit_* method rebuilds one kind of element through the target
    TextElementFactory from a copy of the element's data model."""

    def __init__(self, family: TextElementFactory) -> None:
        self._family = family

    def convert(self, root: Root) -> Root:
        """Returns a new document in the target format; the original is
        not modified."""
        return root.accept(self)

    def _with_children(self, copy: ContainerElement, source: ContainerElement) -> ContainerElement:
        for child in source.children:
            copy.add(child.accept(self))
        return copy

    def visit_root(self, root: Root) -> Root:
        return self._with_children(self._family.create_root(), root)

    def visit_heading(self, heading: Heading) -> Heading:
        return self._with_children(self._family.create_heading(replace(heading.data)), heading)

    def visit_paragraph(self, paragraph: Paragraph) -> Paragraph:
        return self._family.create_paragraph(replace(paragraph.data))

    def visit_link(self, link: Link) -> Link:
        return self._family.create_link(replace(link.data))

    def visit_image(self, image: Image) -> Image:
        return self._family.create_image(replace(image.data))
