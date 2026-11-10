"""BUILDER for documents.

Building a tree by hand means keeping track of which container is the
current parent at every step (create a heading, attach it, remember it,
attach children to it, go back up...). DocumentBuilder hides that:
it keeps a stack of open sections and offers a fluent, step-by-step API

    doc = (DocumentBuilder()
           .heading("Intro")          # opens a section
               .paragraph("Text")     # goes into "Intro"
               .heading("Details", 2) # nested section
                   .link("Docs", "https://...")
               .end()                 # back to "Intro"
           .end()                     # back to the root
           .build())

The builder is format-agnostic: it creates every element through a
TextElementFactory (abstract factory), so the same building steps give
a plain, Markdown or HTML document depending on the factory passed in.
"""

from __future__ import annotations

from .elements import ContainerElement, Root, TextElement
from .families import PlainTextElementFactory, TextElementFactory
from .models import HeadingData, ImageData, LinkData, ParagraphData


class DocumentBuilder:
    def __init__(self, family: TextElementFactory | None = None) -> None:
        self._family = family or PlainTextElementFactory()
        self._root: Root = self._family.create_root()
        self._stack: list[ContainerElement] = [self._root]
        self._built = False

    @property
    def _current(self) -> ContainerElement:
        return self._stack[-1]

    @property
    def depth(self) -> int:
        """How many sections are currently open (0 = at the root)."""
        return len(self._stack) - 1

    def _ensure_open(self) -> None:
        if self._built:
            raise RuntimeError("build() was already called; create a new DocumentBuilder")

    def heading(self, title: str, level: int | None = None) -> "DocumentBuilder":
        """Adds a heading and opens it: following elements go inside it
        until end() is called. Level defaults to one deeper than the
        enclosing section."""
        self._ensure_open()
        heading = self._family.create_heading(HeadingData(title, level or self.depth + 1))
        self._current.add(heading)
        self._stack.append(heading)
        return self

    def end(self) -> "DocumentBuilder":
        """Closes the current section."""
        self._ensure_open()
        if self.depth == 0:
            raise RuntimeError("end() called with no open section")
        self._stack.pop()
        return self

    def paragraph(self, text: str) -> "DocumentBuilder":
        self._ensure_open()
        if text:
            self._current.add(self._family.create_paragraph(ParagraphData(text)))
        return self

    def link(self, label: str, url: str) -> "DocumentBuilder":
        self._ensure_open()
        self._current.add(self._family.create_link(LinkData(label, url)))
        return self

    def image(self, alt_text: str, source: str) -> "DocumentBuilder":
        self._ensure_open()
        self._current.add(self._family.create_image(ImageData(alt_text, source)))
        return self

    def append(self, element: TextElement) -> "DocumentBuilder":
        """Inserts a ready-made element (e.g. a clone of a prototype)."""
        self._ensure_open()
        self._current.add(element)
        return self

    def build(self) -> Root:
        """Returns the finished document. Open sections are closed
        implicitly; the builder can't be reused afterwards."""
        self._ensure_open()
        self._built = True
        return self._root
