"""CLI-level tests for the features built on the creational patterns:
print --format, cp, template and sheet --format."""

import pytest

from cli.framework import CLI, BufferConsole
from cli.text_cli import TextDocumentStrategy, TextNavigator
from core.text import ElementKind


def run(cli, line):
    cli.exec_command(line)


@pytest.fixture
def text_setup():
    nav = TextNavigator()
    intro = nav.create_and_attach(ElementKind.HEADING, title="Intro", level="1")
    nav.cursor = intro
    nav.create_and_attach(ElementKind.PARAGRAPH, text="Hello <world>")
    nav.cursor = nav.root
    cli = CLI(BufferConsole())
    cli.use_strategy(TextDocumentStrategy(nav))
    return nav, cli


def test_print_format_html(text_setup, capsys):
    _, registry = text_setup

    run(registry, "print --format html")

    out = capsys.readouterr().out
    assert "<h1>Intro</h1>" in out
    assert "<p>Hello &lt;world&gt;</p>" in out


def test_print_format_does_not_change_document(text_setup, capsys):
    nav, registry = text_setup
    before = nav.root.render()

    run(registry, "print --format markdown")

    assert nav.root.render() == before


def test_print_unknown_format(text_setup, capsys):
    _, registry = text_setup

    run(registry, "print --format latex")

    assert "Unknown format" in capsys.readouterr().out


def test_cp_duplicates_subtree_with_new_ids(text_setup):
    nav, registry = text_setup

    run(registry, "cp Intro")

    first, second = nav.root.children
    assert first is not second
    assert second.render() == first.render()
    assert nav.display_id(second) == "h2"
    assert nav.display_id(second.children[0]) == "p2"


def test_cp_copy_is_independent(text_setup):
    nav, registry = text_setup
    run(registry, "cp Intro")

    nav.root.children[1].children[0].data.text = "edited"

    assert nav.root.children[0].children[0].data.text == "Hello <world>"


def test_template_save_and_use(text_setup, capsys):
    nav, registry = text_setup
    run(registry, "template save section Intro")
    run(registry, "cd Intro")

    run(registry, "template use section")

    inserted = nav.root.children[0].children[-1]
    assert inserted.title == "Intro"
    assert inserted is not nav.root.children[0]
    run(registry, "template ls")
    assert "section" in capsys.readouterr().out


def test_template_use_unknown(text_setup, capsys):
    _, registry = text_setup

    run(registry, "template use nope")

    assert "No template named" in capsys.readouterr().out


def test_sheet_format_html(chars):
    chars.run("db create albedo")

    html = chars.run("sheet c1 --format html")

    assert html.startswith("<article>\n<section>\n<h1>Albedo</h1>")
    assert "<h2>Talents</h2>" in html
