"""Tests for the CLI layer: the framework (ArgsParser, Args, Command,
strategies, CLI facade, widgets), text navigation and the characters
catalog commands. Dialog answers are fed through BufferConsole."""

import pytest

from cli import build_text_cli
from cli.app import parse_startup
from cli.framework import (
    CLI,
    Args,
    ArgsParser,
    BufferConsole,
    CommandGroup,
    FunctionCommand,
    Mode,
    StaticStrategy,
    Table,
    UsageError,
)
from cli.framework.graphic import Style
from cli.text_cli import TextNavigator
from core.text import ElementKind


# -- startup ------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv, mode",
    [(["--text"], "text"), (["-t"], "text"), (["--chars"], "chars"), (["-c"], "chars"), ([], None)],
)
def test_startup_mode(argv, mode):
    assert parse_startup(argv).mode == mode


def test_startup_offline_and_one_shot_command():
    options = parse_startup(["--chars", "--offline", "db", "chars"])

    assert options.offline
    assert options.command == ["db", "chars"]


# -- ArgsParser / Args ---------------------------------------------------------


def test_parser_splits_command_args_and_options():
    args = ArgsParser().parse("act ability c1 c2 --id a1 -x 5")

    assert args.command == "act"
    assert args.positional == ["ability", "c1", "c2"]
    assert args.options == {"id": "a1", "x": "5"}


def test_parser_keeps_quoted_strings_together():
    assert ArgsParser().parse('add heading "My long title"').positional == ["heading", "My long title"]


def test_parser_flags_without_values_and_equals_form():
    args = ArgsParser().parse("print --whole --id --format=html c1")

    assert args.options == {"whole": "", "id": "", "format": "html"}
    assert args.positional == ["c1"]


def test_parser_negative_numbers_are_positional():
    assert ArgsParser().parse("x -5").positional == ["-5"]


def test_parser_empty_input():
    assert ArgsParser().parse("   ") == Args()


def test_args_helpers():
    args = Args("game", ["start", "x"], {"team": "c1, c2", "n": "3", "i": "42"})

    assert args.option("id", "i") == "42"
    assert args.has("id", "i")
    assert args.list_option("team") == ["c1", "c2"]
    assert args.int_option("n", default=1) == 3
    assert args.shift() == Args("start", ["x"], args.options)


def test_args_int_option_rejects_text():
    with pytest.raises(UsageError):
        Args("x", [], {"n": "many"}).int_option("n", default=1)


# -- CLI facade ----------------------------------------------------------------


@pytest.fixture
def bare():
    console = BufferConsole()
    return CLI(console), console


def test_use_strategy_registers_and_executes_commands(bare):
    cli, console = bare
    calls = []
    cli.use_strategy(StaticStrategy("t", "Test", [
        FunctionCommand("ping", lambda a, c: calls.append(a.positional), "<x>", "test", min_args=1)]))

    assert cli.exec_command("ping hello")
    assert calls == [["hello"]]


def test_unknown_command_is_reported(bare):
    cli, console = bare

    assert not cli.exec_command("nope")
    assert "Unknown command" in console.output


def test_missing_arguments_show_usage(bare):
    cli, console = bare
    cli.use_strategy(StaticStrategy("t", "T", [FunctionCommand("ping", lambda a, c: None, "<x>", "", 1)]))

    assert not cli.exec_command("ping")
    assert "usage: ping <x>" in console.output


def test_duplicate_command_names_are_rejected(bare):
    cli, _ = bare
    strategy = StaticStrategy("a", "A", [FunctionCommand("dup", lambda a, c: None)])
    cli.use_strategy(strategy)

    with pytest.raises(ValueError):
        cli.use_strategy(StaticStrategy("b", "B", [FunctionCommand("dup", lambda a, c: None)]))


def test_remove_strategy_unregisters_its_commands(bare):
    cli, _ = bare
    cli.use_strategy(StaticStrategy("a", "A", [FunctionCommand("x", lambda a, c: None)]))
    cli.remove_strategy("a")

    assert cli.find_command("x") is None


def test_command_errors_are_shown_not_raised(bare):
    cli, console = bare

    def boom(args, c):
        raise ValueError("bad thing")

    cli.use_strategy(StaticStrategy("a", "A", [FunctionCommand("boom", boom)]))

    assert not cli.exec_command("boom")
    assert "bad thing" in console.output


def test_command_group_dispatches_and_lists_subcommands(bare):
    cli, console = bare
    seen = []
    group = CommandGroup("db", "database", [FunctionCommand("chars", lambda a, c: seen.append(a.positional))])
    cli.use_strategy(StaticStrategy("db", "DB", [group]))

    cli.exec_command("db chars --filter x a")
    cli.exec_command("db")

    assert seen == [["a"]]
    assert "db chars" in console.output


def test_modes_switch_available_commands_and_back_returns(bare):
    cli, console = bare
    left = []
    cli.push_mode(Mode("battle", "battle> ", [StaticStrategy("b", "B", [FunctionCommand("hit", lambda a, c: None)])],
                       on_leave=lambda: left.append(True)))

    assert cli.find_command("hit") is not None
    cli.exec_command("back")
    assert cli.find_command("hit") is None
    assert left == [True]


def test_help_lists_strategies(bare):
    cli, console = bare
    cli.use_strategy(StaticStrategy("t", "My category", [FunctionCommand("ping", lambda a, c: None, "", "pong")]))

    cli.exec_command("help")

    assert "My category" in console.output and "pong" in console.output


def test_run_loop_until_exit():
    console = BufferConsole(["help", "exit", "never-run"])
    CLI(console).run()

    assert "> exit" in console.lines
    assert "> never-run" not in console.lines


# -- widgets --------------------------------------------------------------------


def test_table_aligns_columns_and_truncates():
    lines = Table(["A", "Name"], [[1, "x" * 60]], max_width=10).format(Style(False))

    assert lines[0].startswith("  A │ Name")
    assert lines[2].endswith("xxxxxxxxx…")


def test_dialog_reasks_invalid_answers(bare):
    cli, console = bare
    console.feed("abc", "-3", "7")

    assert cli.dialog.ask_int("Age", minimum=0) == 7
    assert console.output.count("!") == 2


def test_dialog_gives_up_when_input_ends(bare):
    cli, console = bare
    from cli.framework import CommandError

    with pytest.raises(CommandError):
        cli.dialog.ask("Name")


# -- text navigator ----------------------------------------------------------------


@pytest.fixture
def nav():
    navigator = TextNavigator()
    intro = navigator.create_and_attach(ElementKind.HEADING, title="Intro", level="1")
    navigator.cursor = intro
    navigator.create_and_attach(ElementKind.HEADING, title="Details", level="2")
    navigator.cursor = navigator.root
    return navigator


def text_cli_for(nav):
    from cli.framework import CLI
    from cli.text_cli import TextDocumentStrategy

    cli = CLI(BufferConsole())
    cli.use_strategy(TextDocumentStrategy(nav))
    return cli


def test_navigator_assigns_sequential_ids(nav):
    assert nav.find_by_id("h1").title == "Intro"
    assert nav.find_by_id("h2").title == "Details"


def test_cd_absolute_path_and_pwd(nav):
    assert nav.go_to_path("/Intro/Details")
    assert nav.pwd() == "/Intro/Details"


def test_cd_to_missing_path_keeps_cursor(nav):
    assert not nav.go_to_path("/Missing")
    assert nav.pwd() == "/"


def test_up_from_root_fails(nav):
    assert not nav.go_up()


def test_cd_by_id_then_up(nav):
    nav.go_to_id("h2")
    nav.go_up()

    assert nav.pwd() == "/Intro"


def test_rm_command_asks_for_confirmation(nav, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    text_cli_for(nav).exec_command("rm Intro")

    assert len(nav.root.children) == 1


def test_rm_command_removes_after_yes(nav, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    text_cli_for(nav).exec_command("rm Intro")

    assert len(nav.root.children) == 0


def test_text_save_and_load_commands(nav, tmp_path):
    path = str(tmp_path / "doc.json")
    text_cli_for(nav).exec_command(f"save {path}")

    fresh = TextNavigator()
    text_cli_for(fresh).exec_command(f"load {path}")

    assert fresh.root.render() == nav.root.render()
    assert fresh.find_by_id("h2").title == "Details"


def test_build_text_cli_has_text_commands():
    cli, _ = build_text_cli(BufferConsole())

    assert cli.find_command("pwd") is not None


# -- characters commands -------------------------------------------------------------

RAGNAR = ["Ragnar", "120", "8", "15", "-", "-", "-"]
ELOWEN = ["Elowen", "80", "2", "6", "Catalyst", "Hydro", "https://example.com/elowen.png"]


def test_create_char_dialog_adds_to_catalog(chars):
    out = chars.run("create char", *RAGNAR)

    assert chars.catalog.find_character("c1").name == "Ragnar"
    assert chars.catalog.find_character("Ragnar") is chars.catalog.find_character("c1")
    assert "Created character 'Ragnar' as [c1]" in out


def test_create_char_rejects_invalid_values_and_duplicate_names(chars):
    chars.run("create char", *RAGNAR)

    out = chars.run("create char", "Ragnar", "Bjorn", "-5", "lots", "100", "", "", "", "", "", "")

    bjorn = chars.catalog.find_character("Bjorn")
    assert bjorn.max_health == 100 and bjorn.armor == 0 and bjorn.attack_power == 10
    assert "name is already taken" in out and "must be at least 1" in out


def test_create_char_stores_optional_fields_and_image_link(chars):
    chars.run("create char", *ELOWEN)

    out = chars.run("show Elowen")

    assert "Catalyst" in out and "Hydro" in out
    assert "https://example.com/elowen.png" in out


def test_create_char_cancelled_when_input_ends(chars):
    out = chars.run("create char", "Half")

    assert "Input cancelled" in out
    assert chars.catalog.find_character("Half") is None


def test_full_combat_scenario_through_commands(chars):
    chars.run("create char", *RAGNAR)
    chars.run("create char", "Elowen", "80", "2", "6", "-", "-", "-")
    chars.run("create ability", "fireball", "22")
    chars.run("add c2 a1")

    chars.run("act attack c1 c2")
    out = chars.run("act ability c2 c1 --id a1")

    assert chars.catalog.find_character("Elowen").health == 67
    assert chars.catalog.find_character("Ragnar").health == 98
    assert "Fireball" in out


def test_legacy_add_options_still_work(chars):
    chars.run("create char", *RAGNAR)
    chars.run("create ability", "2", "")

    out = chars.run("add --char_id c1 --id a1")

    assert "Taught 'Fireball' to Ragnar" in out


def test_ls_lists_characters_in_a_table(chars):
    chars.run("create char", *RAGNAR)

    out = chars.run("ls")

    assert "ID" in out and "c1" in out and "120/120" in out


def test_rm_removes_character_after_confirmation(chars):
    chars.run("create char", *RAGNAR)

    chars.run("rm c1", "n")
    assert chars.catalog.find_character("c1") is not None
    chars.run("rm c1", "y")
    assert chars.catalog.find_character("c1") is None
    assert chars.catalog.find_character("Ragnar") is None


def test_characters_save_and_load(chars, tmp_path):
    chars.run("create char", *RAGNAR)
    path = str(tmp_path / "game.json")

    chars.run(f"save {path}")
    chars.run("rm c1 --yes")
    out = chars.run(f"load {path}")

    assert chars.catalog.find_character("c1").health == 120
    assert "Loaded 1 character(s)" in out
    assert not chars.catalog.dirty


def test_save_without_path_uses_default_location(chars):
    chars.run("create char", *RAGNAR)

    out = chars.run("save")

    assert "catalog.json" in out
    assert chars.run("load").count("Loaded 1") == 1


def test_new_ids_do_not_collide_after_load(chars, tmp_path):
    chars.run("create char", *RAGNAR)
    chars.run(f"save {tmp_path / 's.json'}")
    chars.run(f"load {tmp_path / 's.json'}")

    chars.run("create char", "Second", "", "", "", "", "", "")

    assert chars.catalog.find_character("c1").name == "Ragnar"
    assert chars.catalog.find_character("c2").name == "Second"


def test_load_missing_file_reports_error(chars, tmp_path):
    assert "No such file" in chars.run(f"load {tmp_path / 'missing.json'}")
