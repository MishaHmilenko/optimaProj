"""ABSTRACT FACTORY (+ SINGLETON) for families of text elements.

A document has to be made of elements of one output format: an HTML
heading containing a plain-text paragraph would render as broken HTML.
TextElementFactory declares one creation method per element role, and
each concrete factory returns only elements of its own format. Code
that builds documents receives a factory and never names a concrete
element class, so switching the output format of everything it builds
means passing a different factory - and adding a new format (e.g. LaTeX)
means one new factory plus its element classes, with no changes to the
code that builds documents.

The concrete factories hold no state, so there is no reason to have
more than one of each: they are Singletons (via SingletonMeta), and
`factory_for("html")` always hands out the same HtmlElementFactory.
"""

from __future__ import annotations

from abc import abstractmethod

from .elements import Heading, Image, Link, Paragraph, Root
from .models import HeadingData, ImageData, LinkData, ParagraphData
from .singleton import SingletonMeta
from .variants import (
    HtmlHeading,
    HtmlImage,
    HtmlLink,
    HtmlParagraph,
    HtmlRoot,
    MarkdownHeading,
    MarkdownImage,
    MarkdownLink,
    MarkdownParagraph,
    MarkdownRoot,
)


class TextElementFactory(metaclass=SingletonMeta):
    """Abstract factory: one method per element role."""

    format_name: str = ""

    @abstractmethod
    def create_root(self) -> Root:
        raise NotImplementedError

    @abstractmethod
    def create_heading(self, data: HeadingData) -> Heading:
        raise NotImplementedError

    @abstractmethod
    def create_paragraph(self, data: ParagraphData) -> Paragraph:
        raise NotImplementedError

    @abstractmethod
    def create_link(self, data: LinkData) -> Link:
        raise NotImplementedError

    @abstractmethod
    def create_image(self, data: ImageData) -> Image:
        raise NotImplementedError


class PlainTextElementFactory(TextElementFactory):
    format_name = "plain"

    def create_root(self) -> Root:
        return Root()

    def create_heading(self, data: HeadingData) -> Heading:
        return Heading(data)

    def create_paragraph(self, data: ParagraphData) -> Paragraph:
        return Paragraph(data)

    def create_link(self, data: LinkData) -> Link:
        return Link(data)

    def create_image(self, data: ImageData) -> Image:
        return Image(data)


class MarkdownElementFactory(TextElementFactory):
    format_name = "markdown"

    def create_root(self) -> Root:
        return MarkdownRoot()

    def create_heading(self, data: HeadingData) -> Heading:
        return MarkdownHeading(data)

    def create_paragraph(self, data: ParagraphData) -> Paragraph:
        return MarkdownParagraph(data)

    def create_link(self, data: LinkData) -> Link:
        return MarkdownLink(data)

    def create_image(self, data: ImageData) -> Image:
        return MarkdownImage(data)


class HtmlElementFactory(TextElementFactory):
    format_name = "html"

    def create_root(self) -> Root:
        return HtmlRoot()

    def create_heading(self, data: HeadingData) -> Heading:
        return HtmlHeading(data)

    def create_paragraph(self, data: ParagraphData) -> Paragraph:
        return HtmlParagraph(data)

    def create_link(self, data: LinkData) -> Link:
        return HtmlLink(data)

    def create_image(self, data: ImageData) -> Image:
        return HtmlImage(data)


_FAMILIES: dict[str, type[TextElementFactory]] = {
    PlainTextElementFactory.format_name: PlainTextElementFactory,
    MarkdownElementFactory.format_name: MarkdownElementFactory,
    HtmlElementFactory.format_name: HtmlElementFactory,
}


def available_formats() -> tuple[str, ...]:
    return tuple(_FAMILIES)


def factory_for(format_name: str) -> TextElementFactory:
    """The (singleton) factory for a format name."""
    try:
        return _FAMILIES[format_name.lower()]()
    except KeyError:
        raise ValueError(
            f"Unknown format '{format_name}'. Available: {', '.join(available_formats())}"
        ) from None
