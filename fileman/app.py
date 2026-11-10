"""FileManagerApp: the STATE context and the main loop.

It owns the shared services (file system, terminal, renderer, status
bar), holds the current Mode and switches between modes. The loop is
the same in every state: draw a frame, read a key, give it to the mode.

Exceptional states (errors) never change the state graph: an error
raised while handling a key is reported in the status bar and the user
stays where they were.
"""

from __future__ import annotations

from .canvas import Canvas
from .errors import FileManagerError
from .filesystem import IFileSystem
from .help import build_help
from .keys import Key
from .modes import BrowserMode, EditorMode, Mode, ViewerMode
from .renderer import AnsiRenderer
from .status import StatusBar
from .terminal import ITerminal


class FileManagerApp:
    def __init__(self, fs: IFileSystem, terminal: ITerminal, start_dir: str) -> None:
        self.fs = fs
        self.terminal = terminal
        self.renderer = AnsiRenderer(terminal)
        self.status = StatusBar()
        self.running = True
        # The browser is created once and kept, so returning to it restores
        # the directory and selection the user left.
        self.browser = BrowserMode(self, start_dir)
        self.mode: Mode = self.browser

    # -- state transitions -------------------------------------------------------------------

    def switch(self, mode: Mode) -> None:
        self.mode = mode
        mode.on_enter()

    def back_to_browser(self) -> None:
        self.browser.refresh()  # sizes may have changed while editing
        self.switch(self.browser)

    def open_viewer(self, path: str) -> None:
        if self.fs.is_dir(path):
            raise FileManagerError(f"{path} is a directory")
        text = self.fs.read_text(path)  # raises before any state change
        self._select_in_browser(path)
        self.switch(ViewerMode(self, path, text.splitlines(), path))

    def open_editor(self, path: str) -> None:
        if self.fs.is_dir(path):
            raise FileManagerError(f"{path} is a directory")
        text = self.fs.read_text(path)
        self._select_in_browser(path)
        self.switch(EditorMode(self, path, text))

    def show_help(self) -> None:
        previous = self.mode
        sections = [
            ("File list", self.browser),
            ("Viewer", ViewerMode(self, "", [], path="")),
            ("Editor", EditorMode(self, "", "")),
        ]
        document = build_help(sections, self.browser.commands)
        self.switch(ViewerMode(self, "Help", document.render().splitlines(),
                               on_close=lambda: self.switch(previous)))

    def quit(self) -> None:
        self.running = False

    def _select_in_browser(self, path: str) -> None:
        if self.fs.parent(path) == self.browser.cwd:
            self.browser.select_name(path.rstrip("/").rsplit("/", 1)[-1])

    # -- loop -------------------------------------------------------------------------------------

    def handle_key(self, key: Key) -> None:
        self.status.clear()
        if key.name == "resize":
            return  # the next frame is drawn at the new size anyway
        try:
            self.mode.handle_key(key)
        except (FileManagerError, OSError) as exc:
            self.status.error(str(exc) or type(exc).__name__)

    def frame(self) -> Canvas:
        columns, rows = self.terminal.size()
        canvas = Canvas(columns, rows)
        self.mode.render(canvas)
        return canvas

    def run(self) -> None:
        with self.terminal.session():
            while self.running:
                self.renderer.draw(self.frame())
                self.handle_key(self.terminal.read_key())
