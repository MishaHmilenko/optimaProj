"""Pure data models for the text system.

These carry no behaviour at all (no render(), no I/O) - they only hold
the fields that make up each kind of element. The element classes in
elements.py wrap one of these instead of declaring the same fields
twice, and the Data layer (data/text_serializer.py) converts these
models straight to/from JSON, since they are already plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ElementKind(Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LINK = "link"
    IMAGE = "image"


@dataclass
class HeadingData:
    title: str
    level: int = 1


@dataclass
class ParagraphData:
    text: str


@dataclass
class LinkData:
    label: str
    url: str


@dataclass
class ImageData:
    alt_text: str
    source: str
