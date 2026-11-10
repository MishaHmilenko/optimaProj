"""Unit tests for the text element hierarchy and TextFactory."""

import pytest

from core.text import (
    ElementKind,
    Heading,
    HeadingData,
    Image,
    ImageData,
    Link,
    LinkData,
    Paragraph,
    ParagraphData,
    TextFactory,
)


def test_paragraph_renders_its_text():
    # Arrange
    paragraph = Paragraph(ParagraphData("Hello"))
    # Act
    result = paragraph.render()
    # Assert
    assert result == "Hello"


def test_link_renders_label_and_url():
    link = Link(LinkData("Docs", "https://example.com"))

    result = link.render()

    assert result == "Docs (https://example.com)"


def test_image_renders_alt_text_and_source():
    image = Image(ImageData("Diagram", "diagram.png"))

    result = image.render()

    assert result == "[image: Diagram -> diagram.png]"


@pytest.mark.parametrize("level, expected", [(1, "# Title"), (2, "## Title"), (3, "### Title")])
def test_heading_prefix_matches_level(level, expected):
    heading = Heading(HeadingData("Title", level))

    result = heading.render()

    assert result == expected


def test_heading_rejects_non_positive_level():
    with pytest.raises(ValueError):
        Heading(HeadingData("Bad", 0))


def test_heading_renders_its_children_after_title():
    heading = Heading(HeadingData("Intro", 1))
    heading.add(Paragraph(ParagraphData("Body")))

    result = heading.render()

    assert result == "# Intro\n\nBody"


def test_container_add_sets_parent_for_nested_containers():
    parent = Heading(HeadingData("Parent", 1))
    child = Heading(HeadingData("Child", 2))

    parent.add(child)

    assert child.parent is parent


def test_container_move_reorders_children():
    heading = Heading(HeadingData("H", 1))
    first, second = Paragraph(ParagraphData("A")), Paragraph(ParagraphData("B"))
    heading.add(first)
    heading.add(second)

    heading.move(1, 0)

    assert heading.children == (second, first)


def test_container_remove_returns_removed_element():
    heading = Heading(HeadingData("H", 1))
    paragraph = Paragraph(ParagraphData("A"))
    heading.add(paragraph)

    removed = heading.remove(0)

    assert removed is paragraph
    assert len(heading) == 0


def test_children_view_cannot_mutate_container():
    heading = Heading(HeadingData("H", 1))

    children = heading.children

    assert isinstance(children, tuple)


def test_table_of_contents_includes_nested_headings_with_indent():
    factory = TextFactory()
    root = factory.create_document()
    intro = factory.create_and_attach(root, ElementKind.HEADING, title="Intro", level=1)
    factory.create_and_attach(intro, ElementKind.HEADING, title="Details", level=2)
    factory.create_and_attach(intro, ElementKind.PARAGRAPH, text="ignored in toc")

    toc = root.table_of_contents()

    assert toc == "- Intro\n  - Details"


@pytest.mark.parametrize(
    "kind, fields, expected_type",
    [
        (ElementKind.HEADING, {"title": "T", "level": "2"}, Heading),
        (ElementKind.PARAGRAPH, {"text": "p"}, Paragraph),
        (ElementKind.LINK, {"label": "l", "url": "u"}, Link),
        (ElementKind.IMAGE, {"alt_text": "a", "source": "s"}, Image),
    ],
)
def test_factory_creates_element_of_requested_kind(kind, fields, expected_type):
    factory = TextFactory()

    element = factory.create(kind, **fields)

    assert isinstance(element, expected_type)


def test_factory_create_and_attach_adds_to_parent():
    factory = TextFactory()
    root = factory.create_document()

    paragraph = factory.create_and_attach(root, ElementKind.PARAGRAPH, text="x")

    assert root.children == (paragraph,)
