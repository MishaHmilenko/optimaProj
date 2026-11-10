"""Converts the text document tree to/from a plain JSON-serializable
structure (the storage shape for the text system).

Saving is a VISITOR (SerializingVisitor): one visit_* method per element
kind replaces the former `isinstance` chain. Loading starts from plain
dicts, not elements, so it stays a simple dispatch on the "type" tag.
"""

from __future__ import annotations

from typing import Any

from core.text import ElementKind, Root, TextElement, TextFactory
from core.text.elements import Heading, Image, Link, Paragraph
from core.text.visitor import TextElementVisitor


class SerializingVisitor(TextElementVisitor[dict[str, Any]]):
    def visit_root(self, root: Root) -> dict[str, Any]:
        return {"type": "root", "children": [child.accept(self) for child in root.children]}

    def visit_heading(self, heading: Heading) -> dict[str, Any]:
        return {
            "type": ElementKind.HEADING.value,
            "title": heading.title,
            "level": heading.level,
            "children": [child.accept(self) for child in heading.children],
        }

    def visit_paragraph(self, paragraph: Paragraph) -> dict[str, Any]:
        return {"type": ElementKind.PARAGRAPH.value, "text": paragraph.data.text}

    def visit_link(self, link: Link) -> dict[str, Any]:
        return {"type": ElementKind.LINK.value, "label": link.data.label, "url": link.data.url}

    def visit_image(self, image: Image) -> dict[str, Any]:
        return {"type": ElementKind.IMAGE.value, "alt_text": image.data.alt_text, "source": image.data.source}


def document_to_dict(root: Root) -> dict[str, Any]:
    return root.accept(SerializingVisitor())


def _dict_to_element(factory: TextFactory, node: dict[str, Any]) -> TextElement:
    kind = ElementKind(node["type"])
    if kind is ElementKind.HEADING:
        element = factory.create(kind, title=node["title"], level=node.get("level", 1))
        for child_node in node.get("children", []):
            element.add(_dict_to_element(factory, child_node))
        return element
    if kind is ElementKind.PARAGRAPH:
        return factory.create(kind, text=node["text"])
    if kind is ElementKind.LINK:
        return factory.create(kind, label=node["label"], url=node["url"])
    if kind is ElementKind.IMAGE:
        return factory.create(kind, alt_text=node["alt_text"], source=node["source"])
    raise ValueError(f"Unknown element type: {node['type']}")


def dict_to_document(data: dict[str, Any], factory: TextFactory | None = None) -> Root:
    factory = factory or TextFactory()
    root = factory.create_document()
    for child_node in data.get("children", []):
        root.add(_dict_to_element(factory, child_node))
    return root
