"""Tests for the console file manager (practical 12).

The whole application runs against ScriptedTerminal (fake console) and
MemoryFileSystem (fake disk), so every state transition is checked on
the in-memory Canvas - no real terminal, no real files.
"""

import os

import pytest

import files
from fileman import FileManagerApp, MemoryFileSystem
from fileman.buffer import TextBuffer
from fileman.canvas import Canvas, Style, clip
from fileman.errors import BinaryFileError, FileManagerError, FileTooLargeError
from fileman.filesystem import LocalFileSystem
from fileman.keys import Key, KeyDecoder
from fileman.modes import BrowserMode, ConfirmMode, EditorMode, PromptMode, ViewerMode
from fileman.renderer import AnsiRenderer
from fileman.terminal import AnsiTerminal, ITerminal


class ScriptedTerminal(ITerminal):
    """Fake console: fixed size, scripted key presses, records output."""

    def __init__(self, keys=(), columns=60, rows=14):
        self.keys = list(keys)
        self.columns, self.rows = columns, rows
        self.output = []

    def size(self):
        return self.columns, self.rows

    def write(self, text):
        self.output.append(text)

    def read_key(self):
        return self.keys.pop(0) if self.keys else Key("ctrl+q")


def sample_fs():
    return MemoryFileSystem(
        {
            "/home/notes.txt": "first line\nsecond line\n",
            "/home/long.txt": "\n".join(f"line {n}" for n in range(1, 101)),
            "/home/src/main.py": "def main():\n    pass\n",
            "/home/.env": "SECRET=1",
            "/home/image.bin": "PNG\x00\x01",
        },
        dirs=["/home/empty"],
    )


@pytest.fixture
def app():
    return FileManagerApp(sample_fs(), ScriptedTerminal(), "/home")


def press(app, *names):
    """Presses keys by name: "enter", "ctrl+s", or a single character."""
    for name in names:
        app.handle_key(Key.printable(name) if len(name) == 1 else Key(name))


def type_text(app, text):
    for key in KeyDecoder().decode(text):
        app.handle_key(key)


def screen(app):
    return app.frame()


# -- KeyDecoder ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data, expected",
    [
        ("\x1b[A", "up"), ("\x1bOB", "down"), ("\x1b[C", "right"), ("\x1b[D", "left"),
        ("\x1b[5~", "pageup"), ("\x1b[6~", "pagedown"), ("\x1b[H", "home"), ("\x1b[4~", "end"),
        ("\x1b[3~", "delete"), ("\r", "enter"), ("\x7f", "backspace"), ("\t", "tab"),
        ("\x13", "ctrl+s"), ("\x11", "ctrl+q"), ("\x1a", "ctrl+z"), ("\x1b", "escape"),
        (" ", "space"), ("q", "q"),
    ],
)
def test_decoder_names(data, expected):
    assert [k.name for k in KeyDecoder().decode(data)] == [expected]


def test_decoder_handles_unicode_and_mixed_chunks():
    keys = KeyDecoder().decode("ж\x1b[Ax")

    assert [k.name for k in keys] == ["ж", "up", "x"]
    assert keys[0].is_printable and keys[0].char == "ж"


def test_decoder_skips_unknown_sequences_whole():
    assert [k.name for k in KeyDecoder().decode("\x1b[1;5Za")] == ["unknown", "a"]


def test_escape_followed_by_letter_is_two_keys():
    assert [k.name for k in KeyDecoder().decode("\x1bx")] == ["escape", "x"]


def test_space_key_is_still_typeable():
    key = KeyDecoder().decode(" ")[0]

    assert key.is_printable and key.char == " "


# -- Canvas & renderer -------------------------------------------------------------------------


def test_canvas_regions():
    canvas = Canvas(40, 10)

    assert (canvas.body_top, canvas.body_height, canvas.status_row, canvas.hints_row) == (1, 7, 8, 9)


def test_canvas_clips_to_width():
    canvas = Canvas(20, 8)
    canvas.write(1, "x" * 15)
    canvas.write(1, "y" * 15)

    assert canvas.text(1) == "x" * 15 + "y" * 5


def test_clip_marks_cut():
    assert clip("abcdef", 4) == "abc…"
    assert clip("abc", 4) == "abc"
    assert clip("abc", 0) == ""


def test_renderer_positions_rows_pads_and_shows_cursor():
    canvas = Canvas(20, 8)
    canvas.write_line(0, "Title", Style.HEADER)
    canvas.cursor = (2, 5)

    out = AnsiRenderer(ScriptedTerminal()).to_ansi(canvas)

    assert "\x1b[1;1H\x1b[0;1;30;46mTitle" in out
    assert "\x1b[0;1;30;46m" + " " * 15 in out  # header bar padded in its own colour
    assert out.endswith("\x1b[3;6H\x1b[?25h")


def test_renderer_hides_cursor_without_one():
    out = AnsiRenderer(ScriptedTerminal()).to_ansi(Canvas(20, 8))

    assert out.startswith("\x1b[?25l") and "\x1b[?25h" not in out


# -- TextBuffer ------------------------------------------------------------------------------


def test_buffer_typing_newline_keeps_indent():
    buffer = TextBuffer("    if x:")
    buffer.move_end()

    buffer.newline()
    buffer.insert("pass")

    assert buffer.lines == ["    if x:", "    pass"]
    assert (buffer.row, buffer.col) == (1, 8)


def test_buffer_backspace_and_delete_join_lines():
    buffer = TextBuffer("ab\ncd")
    buffer.move_down()

    buffer.backspace()
    assert buffer.lines == ["abcd"] and buffer.col == 2

    buffer.move_end()
    buffer.delete()  # at the very end: nothing happens
    assert buffer.lines == ["abcd"]


def test_buffer_cursor_wraps_between_lines():
    buffer = TextBuffer("ab\ncd")
    buffer.move_end()
    buffer.move_right()
    assert (buffer.row, buffer.col) == (1, 0)
    buffer.move_left()
    assert (buffer.row, buffer.col) == (0, 2)


def test_buffer_column_is_clamped_on_shorter_line():
    buffer = TextBuffer("long line\nab")
    buffer.move_end()

    buffer.move_down()

    assert buffer.col == 2


def test_buffer_undo_groups_typing_on_one_line():
    buffer = TextBuffer("")
    for char in "hello":
        buffer.insert(char)
    buffer.newline()
    buffer.insert("x")

    buffer.undo()
    assert buffer.lines == ["hello", ""]
    buffer.undo()
    assert buffer.lines == ["hello"]
    buffer.undo()
    assert buffer.lines == [""]
    assert buffer.undo() is False


def test_buffer_modified_flag_and_trailing_newline():
    buffer = TextBuffer("a\n")
    assert not buffer.modified

    buffer.insert("b")
    assert buffer.modified and buffer.text == "ba\n"

    buffer.mark_saved()
    assert not buffer.modified

    buffer.undo()
    assert buffer.modified  # back to text different from the saved one


# -- File systems ----------------------------------------------------------------------------


def test_memory_fs_lists_dirs_first_and_detects_binary():
    fs = sample_fs()

    names = [e.name for e in fs.list_dir("/home")]

    assert names[:2] == ["empty", "src"]
    assert names[2:] == [".env", "image.bin", "long.txt", "notes.txt"]
    with pytest.raises(BinaryFileError):
        fs.read_text("/home/image.bin")


def test_memory_fs_resolve_and_parent():
    fs = sample_fs()

    assert fs.resolve("../etc", "/home/src") == "/home/etc"
    assert fs.parent("/") == "/"


def test_local_fs_round_trip_and_errors(tmp_path, monkeypatch):
    fs = LocalFileSystem()
    (tmp_path / "dir").mkdir()
    fs.write_text(str(tmp_path / "a.txt"), "привіт")
    (tmp_path / "b.bin").write_bytes(b"\x00\xff")

    assert [e.name for e in fs.list_dir(str(tmp_path))] == ["dir", "a.txt", "b.bin"]
    assert fs.read_text(str(tmp_path / "a.txt")) == "привіт"
    with pytest.raises(BinaryFileError):
        fs.read_text(str(tmp_path / "b.bin"))
    monkeypatch.setattr("fileman.filesystem.MAX_TEXT_SIZE", 3)
    with pytest.raises(FileTooLargeError):
        fs.read_text(str(tmp_path / "a.txt"))


# -- Browser state ------------------------------------------------------------------------------


def test_browser_lists_directory_with_parent_entry(app):
    body = screen(app).body_text()

    assert body[0].strip() == ".."
    assert body[1].strip().startswith("empty/")
    assert not any(".env" in line for line in body)  # hidden by default
    assert "BROWSE" in screen(app).text(0) and "/home" in screen(app).text(0)


def test_browser_enters_directory_and_back_keeps_selection(app):
    press(app, "down", "down", "enter")  # .. / empty / src
    assert app.browser.cwd == "/home/src"

    press(app, "backspace")

    assert app.browser.cwd == "/home"
    assert app.browser.selected_entry().name == "src"


def test_root_has_no_parent_entry():
    app = FileManagerApp(sample_fs(), ScriptedTerminal(), "/")

    assert screen(app).body_text()[0].strip() == "home/"


def test_empty_directory_message(app):
    press(app, "down", "enter")

    assert "(empty directory)" in screen(app).body_text()[1]


def test_toggle_hidden_files(app):
    press(app, ".")

    assert any(".env" in line for line in screen(app).body_text())


def test_selection_scrolls_into_view():
    fs = MemoryFileSystem({f"/d/file{n:02}.txt": "" for n in range(30)})
    app = FileManagerApp(fs, ScriptedTerminal(rows=10), "/d")

    press(app, "end")

    body = screen(app).body_text()
    assert "file29.txt" in body[-1]


def test_open_file_switches_to_viewer(app):
    app.browser.select_name("notes.txt")

    press(app, "enter")

    assert isinstance(app.mode, ViewerMode)
    assert screen(app).body_text()[:2] == [" 1 first line", " 2 second line"]


def test_binary_file_reports_error_and_stays(app):
    press(app, ".")
    app.browser.select_name("image.bin")

    press(app, "enter")

    assert app.mode is app.browser
    assert app.status.is_error and "not a text file" in screen(app).text(screen(app).status_row)


def test_status_message_clears_on_next_key(app):
    press(app, ".")
    assert app.status.text

    press(app, "down")

    assert app.status.text == ""


def test_new_file_through_prompt(app):
    press(app, "n")
    assert isinstance(app.mode, PromptMode)
    type_text(app, "todo.md")
    assert "New file: todo.md" in screen(app).text(screen(app).status_row)

    press(app, "enter")

    assert app.fs.read_text("/home/todo.md") == ""
    assert app.browser.selected_entry().name == "todo.md"
    assert app.mode is app.browser


def test_prompt_escape_cancels(app):
    press(app, "n")
    type_text(app, "x")

    press(app, "escape")

    assert app.mode is app.browser and not app.fs.exists("/home/x")


def test_command_line_cd_and_open(app):
    press(app, ":")
    type_text(app, "cd src")
    press(app, "enter")
    assert app.browser.cwd == "/home/src"

    press(app, ":")
    type_text(app, "open main.py")
    press(app, "enter")
    assert isinstance(app.mode, ViewerMode) and app.mode.path == "/home/src/main.py"


def test_command_line_errors_are_reported(app):
    for line in ("cd nowhere", "frobnicate", "cd"):
        press(app, ":")
        type_text(app, line)
        press(app, "enter")
        assert app.status.is_error, line
        assert app.browser.cwd == "/home"


def test_quit_from_browser(app):
    press(app, "q")

    assert not app.running


# -- Viewer state -------------------------------------------------------------------------------


def open_long(app):
    app.browser.select_name("long.txt")
    press(app, "enter")
    return app.mode


def test_viewer_scrolls_within_bounds(app):
    viewer = open_long(app)
    height = screen(app).body_height

    press(app, "pagedown")
    assert screen(app).body_text()[0].strip().startswith(f"{height + 1} ")

    press(app, "end")
    assert viewer.viewport.top == 100 - height
    press(app, "down")
    assert viewer.viewport.top == 100 - height

    press(app, "home", "up")
    assert viewer.viewport.top == 0


def test_viewer_position_in_status_line(app):
    open_long(app)

    assert "lines 1-11 of 100 (11%)" in screen(app).text(screen(app).status_row)


def test_viewer_escape_returns_to_browser(app):
    open_long(app)

    press(app, "escape")

    assert app.mode is app.browser
    assert app.browser.selected_entry().name == "long.txt"


def test_viewer_e_opens_editor(app):
    open_long(app)

    press(app, "e")

    assert isinstance(app.mode, EditorMode)


# -- Editor state -------------------------------------------------------------------------------


def open_editor(app, name="notes.txt"):
    app.browser.select_name(name)
    press(app, "e")
    return app.mode


def test_editing_and_saving(app):
    editor = open_editor(app)
    press(app, "end")
    type_text(app, "!")
    assert "EDIT *" in screen(app).text(0)

    press(app, "ctrl+s")

    assert app.fs.read_text("/home/notes.txt") == "first line!\nsecond line\n"
    assert "EDIT *" not in screen(app).text(0)
    assert "Saved" in screen(app).text(screen(app).status_row)
    assert not editor.buffer.modified


def test_typed_keys_that_are_bound_elsewhere_are_just_text(app):
    open_editor(app)

    type_text(app, "q?e:n ")

    assert app.fs.read_text("/home/notes.txt") == "first line\nsecond line\n"
    assert app.mode.buffer.lines[0] == "q?e:n first line"
    assert app.running


def test_escape_without_changes_goes_to_viewer(app):
    open_editor(app)

    press(app, "escape")

    assert isinstance(app.mode, ViewerMode)


def test_escape_with_changes_asks_and_discard_keeps_file(app):
    open_editor(app)
    type_text(app, "X")

    press(app, "escape")
    assert isinstance(app.mode, ConfirmMode)
    assert "Save changes" in screen(app).text(screen(app).status_row)

    press(app, "n")

    assert isinstance(app.mode, ViewerMode)
    assert app.fs.read_text("/home/notes.txt") == "first line\nsecond line\n"
    assert app.mode.lines[0] == "first line"


def test_escape_with_changes_and_save(app):
    open_editor(app)
    type_text(app, "X")

    press(app, "escape", "y")

    assert isinstance(app.mode, ViewerMode)
    assert app.fs.read_text("/home/notes.txt").startswith("Xfirst line")


def test_confirm_escape_returns_to_editor_with_changes(app):
    editor = open_editor(app)
    type_text(app, "X")

    press(app, "escape", "escape")

    assert app.mode is editor and editor.buffer.modified


def test_quit_with_unsaved_changes_asks_first(app):
    open_editor(app)
    type_text(app, "X")

    press(app, "ctrl+q")
    assert app.running

    press(app, "n")
    assert not app.running


def test_editor_undo(app):
    open_editor(app)
    type_text(app, "abc")

    press(app, "ctrl+z")

    assert app.mode.buffer.lines[0] == "first line"


def test_editor_cursor_is_placed_on_screen(app):
    open_editor(app)
    press(app, "down", "end")

    canvas = screen(app)

    # gutter " 2 " is 3 wide, "second line" is 11 chars
    assert canvas.cursor == (canvas.body_top + 1, 3 + 11)


def test_editor_scrolls_horizontally():
    fs = MemoryFileSystem({"/w.txt": "x" * 200})
    app = FileManagerApp(fs, ScriptedTerminal(columns=40), "/")
    app.open_editor("/w.txt")

    press(app, "end")

    canvas = screen(app)
    assert canvas.cursor[1] < canvas.width
    assert canvas.body_text()[0].endswith("x")


def test_cannot_edit_directory(app):
    with pytest.raises(FileManagerError):
        app.open_editor("/home/src")


# -- Help --------------------------------------------------------------------------------------


def test_help_is_built_from_key_maps_and_returns_to_previous_mode(app):
    open_long(app)
    viewer = app.mode

    press(app, "?")
    text = "\n".join(app.mode.lines)

    assert "## File list" in text and "## Editor" in text
    assert "ctrl+s" in text and "save" in text
    assert "cd <dir>" in text
    press(app, "escape")
    assert app.mode is viewer


def test_help_document_cannot_be_edited(app):
    press(app, "?", "e")

    assert app.status.is_error and isinstance(app.mode, ViewerMode)


# -- Main loop & real terminal pieces --------------------------------------------------------------


def test_run_loop_draws_frames_until_quit():
    terminal = ScriptedTerminal([Key("down"), Key("resize"), Key("q")])
    app = FileManagerApp(sample_fs(), terminal, "/home")

    app.run()

    assert not app.running
    assert len(terminal.output) == 3  # one frame before each key
    assert "FileMan" in terminal.output[-1]


def test_ansi_terminal_reads_keys_from_a_pipe():
    read_fd, write_fd = os.pipe()
    os.write(write_fd, "\x1b[Bж".encode())
    with os.fdopen(read_fd, "r") as stdin, open(os.devnull, "w") as stdout:
        terminal = AnsiTerminal(stdin=stdin, stdout=stdout)

        keys = [terminal.read_key(), terminal.read_key()]

        assert [k.name for k in keys] == ["down", "ж"]
        assert terminal.size() == (80, 24)  # not a tty: safe default
    os.close(write_fd)


def test_entry_point_refuses_non_interactive_terminal(capsys):
    assert files.main([]) == 1
    assert "interactive terminal" in capsys.readouterr().err
