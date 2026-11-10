"""Tests for the creational patterns added to the text system:
Singleton, Abstract Factory, Builder and Prototype."""

import threading

import pytest

from core.text import (
    DocumentBuilder,
    DocumentConverter,
    ElementKind,
    Heading,
    HeadingData,
    HtmlElementFactory,
    Link,
    MarkdownElementFactory,
    Paragraph,
    ParagraphData,
    PlainTextElementFactory,
    PrototypeRegistry,
    Root,
    SingletonMeta,
    TextElementFactory,
    TextFactory,
    available_formats,
    factory_for,
)
from core.text.variants import HtmlHeading, HtmlParagraph, MarkdownLink


def sample_document(family=None) -> Root:
    return (
        DocumentBuilder(family)
        .heading("Intro")
        .paragraph("Body & more")
        .heading("Links")
        .link("Docs", "https://x.y/?a=1&b=2")
        .image("Logo", "logo.png")
        .end()
        .end()
        .build()
    )


# -- Singleton -------------------------------------------------------------------


@pytest.mark.parametrize(
    "factory_class", [PlainTextElementFactory, MarkdownElementFactory, HtmlElementFactory]
)
def test_each_factory_is_a_singleton(factory_class):
    assert factory_class() is factory_class()


def test_different_factories_are_different_instances():
    assert PlainTextElementFactory() is not HtmlElementFactory()


def test_factory_for_returns_the_singleton():
    assert factory_for("html") is HtmlElementFactory()
    assert factory_for("HTML") is HtmlElementFactory()


def test_singleton_is_created_once_under_concurrency():
    class Counter(metaclass=SingletonMeta):
        created = 0

        def __init__(self):
            Counter.created += 1

    instances = []
    threads = [threading.Thread(target=lambda: instances.append(Counter())) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert Counter.created == 1
    assert all(instance is instances[0] for instance in instances)


def test_abstract_factory_cannot_be_instantiated():
    with pytest.raises(TypeError):
        TextElementFactory()


# -- Abstract Factory ----------------------------------------------------------------


def test_factory_for_unknown_format_raises():
    with pytest.raises(ValueError):
        factory_for("latex")


def test_available_formats():
    assert available_formats() == ("plain", "markdown", "html")


@pytest.mark.parametrize("format_name", ["plain", "markdown", "html"])
def test_family_elements_keep_their_role_types(format_name):
    family = factory_for(format_name)

    heading = family.create_heading(HeadingData("T", 1))
    paragraph = family.create_paragraph(ParagraphData("p"))

    assert isinstance(heading, Heading)
    assert isinstance(paragraph, Paragraph)
    assert isinstance(family.create_root(), Root)


def test_html_family_produces_html_elements():
    family = HtmlElementFactory()

    assert isinstance(family.create_heading(HeadingData("T", 1)), HtmlHeading)
    assert isinstance(family.create_paragraph(ParagraphData("p")), HtmlParagraph)


def test_plain_render_is_unchanged():
    assert sample_document().render() == (
        "# Intro\n\nBody & more\n\n## Links\n\n"
        "Docs (https://x.y/?a=1&b=2)\n\n[image: Logo -> logo.png]"
    )


def test_markdown_render():
    text = sample_document(MarkdownElementFactory()).render()

    assert "[Docs](https://x.y/?a=1&b=2)" in text
    assert "![Logo](logo.png)" in text
    assert text.startswith("# Intro")


def test_html_render_escapes_and_nests():
    html = sample_document(HtmlElementFactory()).render()

    assert html.startswith("<article>\n<section>\n<h1>Intro</h1>")
    assert "<p>Body &amp; more</p>" in html
    assert '<a href="https://x.y/?a=1&amp;b=2">Docs</a>' in html
    assert '<img src="logo.png" alt="Logo">' in html
    assert html.count("<section>") == html.count("</section>") == 2


def test_text_factory_uses_its_family():
    factory = TextFactory(MarkdownElementFactory())

    link = factory.create(ElementKind.LINK, label="a", url="b")

    assert isinstance(link, MarkdownLink)
    assert factory.family is MarkdownElementFactory()


def test_text_factory_defaults_to_plain():
    assert TextFactory().family is PlainTextElementFactory()


def test_table_of_contents_is_format_independent():
    assert sample_document(HtmlElementFactory()).table_of_contents() == sample_document().table_of_contents()


def test_converter_rebuilds_document_in_target_format():
    plain = sample_document()

    html = DocumentConverter(HtmlElementFactory()).convert(plain)

    assert html.render() == sample_document(HtmlElementFactory()).render()


def test_converter_leaves_original_untouched():
    plain = sample_document()
    before = plain.render()

    converted = DocumentConverter(HtmlElementFactory()).convert(plain)
    converted.children[0].data.title = "Changed"

    assert plain.render() == before


# -- Builder -------------------------------------------------------------------------


def test_builder_nests_elements_under_open_heading():
    doc = sample_document()

    intro = doc.children[0]
    links = intro.children[1]
    assert isinstance(links, Heading)
    assert links.level == 2
    assert links.parent is intro
    assert isinstance(links.children[0], Link)


def test_builder_heading_level_defaults_to_depth():
    doc = DocumentBuilder().heading("A").heading("B").heading("C").build()

    levels = []
    node = doc
    while node.children:
        node = node.children[0]
        levels.append(node.level)
    assert levels == [1, 2, 3]


def test_builder_explicit_level_overrides_depth():
    doc = DocumentBuilder().heading("A", 3).build()

    assert doc.children[0].level == 3


def test_builder_end_at_root_raises():
    with pytest.raises(RuntimeError):
        DocumentBuilder().end()


def test_builder_cannot_be_reused_after_build():
    builder = DocumentBuilder().paragraph("x")
    builder.build()

    with pytest.raises(RuntimeError):
        builder.paragraph("y")


def test_builder_skips_empty_paragraphs():
    doc = DocumentBuilder().paragraph("").paragraph("x").build()

    assert len(doc.children) == 1


def test_builder_depth_tracks_open_sections():
    builder = DocumentBuilder().heading("A").heading("B")
    assert builder.depth == 2

    builder.end()
    assert builder.depth == 1


def test_builder_append_inserts_ready_element():
    paragraph = Paragraph(ParagraphData("ready"))

    doc = DocumentBuilder().heading("A").append(paragraph).build()

    assert doc.children[0].children == (paragraph,)


# -- Prototype -----------------------------------------------------------------------


def test_clone_is_deep_and_independent():
    original = sample_document().children[0]

    copy = original.clone()
    copy.children[0].data.text = "changed"
    copy.add(Paragraph(ParagraphData("extra")))

    assert original.children[0].data.text == "Body & more"
    assert len(original.children) == 2
    assert copy.render() != original.render()


def test_clone_renders_identically():
    original = sample_document()

    assert original.clone().render() == original.render()


def test_clone_is_detached_but_internally_linked():
    intro = sample_document().children[0]

    copy = intro.clone()

    assert copy.parent is None
    assert copy.children[1].parent is copy


def test_clone_keeps_format_variant():
    html_heading = sample_document(HtmlElementFactory()).children[0]

    copy = html_heading.clone()

    assert type(copy) is HtmlHeading
    assert all(type(a) is type(b) for a, b in zip(copy.children, html_heading.children))


def test_registry_hands_out_fresh_copies():
    registry = PrototypeRegistry()
    registry.register("note", Paragraph(ParagraphData("Disclaimer")))

    first, second = registry.create("note"), registry.create("note")

    assert first is not second
    assert first.render() == second.render() == "Disclaimer"


def test_registry_keeps_private_copy_of_prototype():
    source = Paragraph(ParagraphData("v1"))
    registry = PrototypeRegistry()
    registry.register("note", source)

    source.data.text = "v2"

    assert registry.create("note").render() == "v1"


def test_registry_unknown_name_raises():
    with pytest.raises(ValueError):
        PrototypeRegistry().create("missing")


def test_registry_names_and_unregister():
    registry = PrototypeRegistry()
    registry.register("b", Paragraph(ParagraphData("b")))
    registry.register("a", Paragraph(ParagraphData("a")))
    registry.unregister("b")

    assert registry.names() == ("a",)
