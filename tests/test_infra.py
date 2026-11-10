"""Tests for the real IDisplayer implementations."""

from infra import ConsoleDisplayer, FileDisplayer, Message, SilentDisplayer


def test_message_to_display_returns_text():
    assert Message("hi").to_display() == "hi"


def test_console_displayer_prints(capsys):
    ConsoleDisplayer().display(Message("hello"))

    assert capsys.readouterr().out == "hello\n"


def test_file_displayer_appends_lines(tmp_path):
    path = tmp_path / "log.txt"
    displayer = FileDisplayer(str(path))

    displayer.display(Message("one"))
    displayer.display(Message("two"))

    assert path.read_text(encoding="utf-8") == "one\ntwo\n"


def test_silent_displayer_outputs_nothing(capsys):
    SilentDisplayer().display(Message("hidden"))

    assert capsys.readouterr().out == ""
