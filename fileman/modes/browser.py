"""BrowserMode: lists a directory and moves around the file system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cli.framework import Args, ArgsParser, Command, FunctionCommand

from ..canvas import Canvas, Style, clip
from ..errors import FileManagerError
from ..filesystem import Entry
from ..viewport import Viewport
from .base import Mode
from .prompt import PromptMode

if TYPE_CHECKING:
    from ..app import FileManagerApp

PARENT = ".."


def human_size(size: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if size < 1024 or unit == "G":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size}"


class BrowserMode(Mode):
    name = "browse"

    def __init__(self, app: "FileManagerApp", start_dir: str) -> None:
        self.cwd = start_dir
        self.entries: list[Entry] = []
        self.selected = 0
        self.show_hidden = False
        self.viewport = Viewport()
        self._page = 10
        super().__init__(app)
        self.commands = self._build_command_line()
        self.refresh()

    # -- keys -------------------------------------------------------------------------------

    def bind_keys(self) -> None:
        self.bind("up k", lambda: self.move(-1), "move selection up")
        self.bind("down j", lambda: self.move(1), "move selection down")
        self.bind("pageup", lambda: self.move(-self._page), "page up")
        self.bind("pagedown", lambda: self.move(self._page), "page down")
        self.bind("home", lambda: self.move_to(0), "first entry")
        self.bind("end", lambda: self.move_to(len(self.rows()) - 1), "last entry")
        self.bind("enter right l", self.open_selected, "open directory / view file")
        self.bind("backspace left h", self.go_up, "go to parent directory")
        self.bind("e", self.edit_selected, "edit selected file")
        self.bind("n", self.prompt_new_file, "create a new file")
        self.bind("d", self.prompt_new_dir, "create a new directory")
        self.bind(".", self.toggle_hidden, "show / hide hidden files")
        self.bind("r", self.refresh, "refresh")
        self.bind(":", self.prompt_command, "command line (cd, open, edit, new, mkdir, q)")
        self.bind("?", self.app.show_help, "help")
        self.bind("q ctrl+q ctrl+c", self.app.quit, "quit")

    # -- command line (reuses the CLI parser + registry) ---------------------------------------

    def _build_command_line(self) -> list[Command]:
        def cmd(name, handler, usage, description):
            return FunctionCommand(name, lambda args, _cli: handler(args), usage, description)

        return [
            cmd("cd", lambda a: self.change_dir(self._arg(a)), "<dir>", "change directory"),
            cmd("open", lambda a: self.app.open_viewer(self._path(a)), "<file>", "view a file"),
            cmd("edit", lambda a: self.app.open_editor(self._path(a)), "<file>", "edit a file"),
            cmd("new", lambda a: self.create_file(self._arg(a)), "<file>", "create a file"),
            cmd("mkdir", lambda a: self.create_dir(self._arg(a)), "<dir>", "create a directory"),
            cmd("q", lambda a: self.app.quit(), "", "quit"),
        ]

    @staticmethod
    def _arg(args: Args) -> str:
        if not args.positional:
            raise FileManagerError("This command needs an argument")
        return args.positional[0]

    def _path(self, args: Args) -> str:
        return self.app.fs.resolve(self._arg(args), self.cwd)

    def run_command(self, line: str) -> None:
        args = ArgsParser().parse(line)
        if not args.command:
            return
        command = next((c for c in self.commands if args.command in c.names), None)
        if command is None:
            raise FileManagerError(f"Unknown command: {args.command}")
        command.execute(args, None)

    def prompt_command(self) -> None:
        self.app.switch(PromptMode(self.app, self, ":", on_submit=self.run_command))

    # -- listing -------------------------------------------------------------------------------

    def rows(self) -> list[Entry]:
        visible = [e for e in self.entries if self.show_hidden or not e.is_hidden]
        parent = self.app.fs.parent(self.cwd)
        if parent != self.cwd:
            return [Entry(PARENT, parent, True)] + visible
        return visible

    def refresh(self) -> None:
        self.entries = self.app.fs.list_dir(self.cwd)
        self.selected = Viewport.clamp(self.selected, len(self.rows()))

    def selected_entry(self) -> Entry | None:
        rows = self.rows()
        return rows[self.selected] if rows else None

    def select_name(self, name: str) -> None:
        for index, entry in enumerate(self.rows()):
            if entry.name == name:
                self.selected = index
                return

    # -- actions ----------------------------------------------------------------------------------

    def move(self, delta: int) -> None:
        self.move_to(self.selected + delta)

    def move_to(self, index: int) -> None:
        self.selected = Viewport.clamp(index, len(self.rows()))

    def change_dir(self, path: str) -> None:
        target = self.app.fs.resolve(path, self.cwd)
        if not self.app.fs.is_dir(target):
            raise FileManagerError(f"Not a directory: {path}")
        entries = self.app.fs.list_dir(target)  # fails before changing state
        previous = self.cwd
        self.cwd, self.entries, self.selected = target, entries, 0
        self.viewport.top = 0
        if self.app.fs.parent(previous) == target:  # went up: keep the old dir selected
            self.select_name(previous.rstrip("/").rsplit("/", 1)[-1])

    def go_up(self) -> None:
        self.change_dir(self.app.fs.parent(self.cwd))

    def open_selected(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            return
        if entry.is_dir:
            self.change_dir(entry.path)
        else:
            self.app.open_viewer(entry.path)

    def edit_selected(self) -> None:
        entry = self.selected_entry()
        if entry is not None and not entry.is_dir:
            self.app.open_editor(entry.path)

    def toggle_hidden(self) -> None:
        current = self.selected_entry()
        self.show_hidden = not self.show_hidden
        self.selected = 0
        if current:
            self.select_name(current.name)
        self.app.status.info("Hidden files shown" if self.show_hidden else "Hidden files hidden")

    def create_file(self, name: str) -> None:
        path = self.app.fs.resolve(name, self.cwd)
        self.app.fs.create_file(path)
        self.refresh()
        self.select_name(name)
        self.app.status.info(f"Created {name}")

    def create_dir(self, name: str) -> None:
        self.app.fs.make_dir(self.app.fs.resolve(name, self.cwd))
        self.refresh()
        self.select_name(name)
        self.app.status.info(f"Created directory {name}")

    def prompt_new_file(self) -> None:
        self.app.switch(PromptMode(self.app, self, "New file: ", on_submit=self.create_file))

    def prompt_new_dir(self) -> None:
        self.app.switch(PromptMode(self.app, self, "New directory: ", on_submit=self.create_dir))

    # -- drawing --------------------------------------------------------------------------------

    def location(self) -> str:
        return self.cwd

    def render_body(self, canvas: Canvas) -> None:
        self._page = max(canvas.body_height - 1, 1)
        rows = self.rows()
        self.viewport.follow(self.selected, canvas.body_height)
        size_width = 8
        name_width = canvas.width - size_width - 3
        is_empty = all(entry.name == PARENT for entry in rows)  # only ".." (or nothing)
        for offset in range(canvas.body_height):
            screen_row = canvas.body_top + offset
            index = self.viewport.top + offset
            if index >= len(rows):
                canvas.clear_row(screen_row)
                if is_empty and index == len(rows):
                    canvas.write(screen_row, "  (empty directory)", Style.MUTED)
                continue
            entry = rows[index]
            label = entry.name + ("/" if entry.is_dir and entry.name != PARENT else "")
            size = "" if entry.is_dir else human_size(entry.size)
            line = f" {clip(label, name_width):<{name_width}} {size:>{size_width}} "
            if index == self.selected:
                canvas.write_line(screen_row, line, Style.SELECTED)
            else:
                canvas.write_line(screen_row, line, Style.DIRECTORY if entry.is_dir else Style.NORMAL)
                canvas.rows[screen_row].fill = Style.NORMAL

    def hints(self) -> list[tuple[str, str]]:
        return [("Enter", "Open"), ("e", "Edit"), ("Bksp", "Up"), ("n", "New"),
                (":", "Cmd"), ("?", "Help"), ("q", "Quit")]
