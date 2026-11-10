#!/usr/bin/env python3
"""Entry point of the file manager.

    python3 files.py            start in the current directory
    python3 files.py <dir>      start in <dir>
    python3 files.py <file>     open <file> in the viewer

Composition root: the only place that picks the real implementations
(LocalFileSystem, AnsiTerminal).
"""

from __future__ import annotations

import os
import sys

from fileman import AnsiTerminal, FileManagerApp, LocalFileSystem


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("FileMan needs an interactive terminal (Linux / macOS).", file=sys.stderr)
        return 1

    fs = LocalFileSystem()
    target = fs.resolve(argv[0] if argv else ".", os.getcwd())
    if not fs.exists(target):
        print(f"No such file or directory: {target}", file=sys.stderr)
        return 1

    start_dir = target if fs.is_dir(target) else fs.parent(target)
    app = FileManagerApp(fs, AnsiTerminal(), start_dir)
    if not fs.is_dir(target):
        app.open_viewer(target)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
