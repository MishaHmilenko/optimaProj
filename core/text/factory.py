"""TextFactory: creates elements by ElementKind selector.

The ElementKind -> builder mapping (from the SOLID practical) is kept,
but the builders no longer instantiate concrete classes themselves:
they ask the TextElementFactory (abstract factory) they were given. So
the same TextFactory API produces plain, Markdown or HTML elements
depending on the family it was constructed with; plain is the default,
which keeps every existing caller working unchanged.
"""

from __future__ import annotations

from typing import Callable

from .elements import ContainerElement, Root, TextElement
from .families import PlainTextElementFactory, TextElementFactory
from .models import ElementKind, HeadingData, ImageData, LinkData, ParagraphData


class TextFactory:
    def __init__(self, family: TextElementFactory | None = None) -> None:
        self._family = family or PlainTextElementFactory()
        family = self._family
        self._builders: dict[ElementKind, Callable[..., TextElement]] = {
            ElementKind.HEADING: lambda **f: family.create_heading(
                HeadingData(title=f["title"], level=int(f.get("level", 1)))
            ),
            ElementKind.PARAGRAPH: lambda **f: family.create_paragraph(ParagraphData(text=f["text"])),
            ElementKind.LINK: lambda **f: family.create_link(LinkData(label=f["label"], url=f["url"])),
            ElementKind.IMAGE: lambda **f: family.create_image(
                ImageData(alt_text=f["alt_text"], source=f["source"])
            ),
        }

    @property
    def family(self) -> TextElementFactory:
        return self._family

    def create_document(self) -> Root:
        return self._family.create_root()

    def create(self, kind: ElementKind, **fields: str) -> TextElement:
        builder = self._builders.get(kind)
        if builder is None:
            raise ValueError(f"Unknown element kind: {kind}")
        return builder(**fields)

    def create_and_attach(self, parent: ContainerElement, kind: ElementKind, **fields: str) -> TextElement:
        element = self.create(kind, **fields)
        parent.add(element)
        return element
