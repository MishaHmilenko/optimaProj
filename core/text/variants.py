"""Markdown and HTML variants of the text elements.

Each variant subclasses the plain element of the same role and only
overrides render(), so every other part of the system (navigation,
table of contents, serialization via isinstance checks, cloning) keeps
working with them unchanged. They are never instantiated directly by
client code - the matching concrete factory in families.py does that.
"""

from __future__ import annotations

from html import escape

from .elements import Heading, Image, Link, Paragraph, Root

# -- Markdown -------------------------------------------------------------------


class MarkdownParagraph(Paragraph):
    pass  # plain paragraphs are already valid Markdown


class MarkdownLink(Link):
    def render(self) -> str:
        return f"[{self.data.label}]({self.data.url})"


class MarkdownImage(Image):
    def render(self) -> str:
        return f"![{self.data.alt_text}]({self.data.source})"


class MarkdownHeading(Heading):
    pass  # "# Title" rendering is already Markdown


class MarkdownRoot(Root):
    pass


# -- HTML -----------------------------------------------------------------------


class HtmlParagraph(Paragraph):
    def render(self) -> str:
        return f"<p>{escape(self.data.text)}</p>"


class HtmlLink(Link):
    def render(self) -> str:
        return f'<p><a href="{escape(self.data.url)}">{escape(self.data.label)}</a></p>'


class HtmlImage(Image):
    def render(self) -> str:
        return f'<img src="{escape(self.data.source)}" alt="{escape(self.data.alt_text)}">'


class HtmlHeading(Heading):
    def render(self) -> str:
        tag = f"h{min(self.level, 6)}"
        parts = [f"<{tag}>{escape(self.title)}</{tag}>"]
        parts += [child.render() for child in self.children]
        return "<section>\n" + "\n".join(parts) + "\n</section>"


class HtmlRoot(Root):
    def render(self) -> str:
        body = "\n".join(child.render() for child in self.children)
        return f"<article>\n{body}\n</article>"
