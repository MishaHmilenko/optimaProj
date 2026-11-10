"""File system access behind an interface.

Modes never call os/pathlib directly: they get an IFileSystem. The real
one is LocalFileSystem; MemoryFileSystem keeps a whole directory tree in
a dict, which makes the browser/viewer/editor fully testable and
deterministic (and safe - tests never touch the real disk).
"""

from __future__ import annotations

import posixpath
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .errors import BinaryFileError, FileManagerError, FileTooLargeError

MAX_TEXT_SIZE = 2 * 1024 * 1024


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified: datetime | None = None

    @property
    def is_hidden(self) -> bool:
        return self.name.startswith(".")


def sort_entries(entries: list[Entry]) -> list[Entry]:
    """Directories first, then files; case-insensitive by name."""
    return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))


class IFileSystem(ABC):
    @abstractmethod
    def list_dir(self, path: str) -> list[Entry]:
        raise NotImplementedError

    @abstractmethod
    def read_text(self, path: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def write_text(self, path: str, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_dir(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def make_dir(self, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, path: str, base: str) -> str:
        """Absolute, normalised form of `path` relative to `base`."""
        raise NotImplementedError

    @abstractmethod
    def parent(self, path: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def join(self, directory: str, name: str) -> str:
        raise NotImplementedError

    def create_file(self, path: str) -> None:
        if self.exists(path):
            raise FileManagerError(f"{path} already exists")
        self.write_text(path, "")


class LocalFileSystem(IFileSystem):
    def list_dir(self, path: str) -> list[Entry]:
        entries = []
        for child in Path(path).iterdir():
            try:
                stat = child.stat()
                entries.append(Entry(child.name, str(child), child.is_dir(), stat.st_size,
                                     datetime.fromtimestamp(stat.st_mtime)))
            except OSError:
                entries.append(Entry(child.name, str(child), False))  # e.g. a broken link
        return sort_entries(entries)

    def read_text(self, path: str) -> str:
        file = Path(path)
        if file.stat().st_size > MAX_TEXT_SIZE:
            raise FileTooLargeError(path, MAX_TEXT_SIZE)
        data = file.read_bytes()
        if b"\x00" in data:
            raise BinaryFileError(path)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise BinaryFileError(path) from None

    def write_text(self, path: str, text: str) -> None:
        Path(path).write_text(text, encoding="utf-8")

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def is_dir(self, path: str) -> bool:
        return Path(path).is_dir()

    def make_dir(self, path: str) -> None:
        Path(path).mkdir()

    def resolve(self, path: str, base: str) -> str:
        return str((Path(base) / Path(path).expanduser()).resolve())

    def parent(self, path: str) -> str:
        return str(Path(path).parent)

    def join(self, directory: str, name: str) -> str:
        return str(Path(directory) / name)


class MemoryFileSystem(IFileSystem):
    """In-memory POSIX-style tree: {"/docs/a.txt": "text", ...}.
    Parent directories of every file are created automatically."""

    def __init__(self, files: dict[str, str] | None = None, dirs: list[str] | None = None) -> None:
        self._files: dict[str, str] = {}
        self._dirs: set[str] = {"/"}
        for directory in dirs or []:
            self._add_dir(self._norm(directory))
        for path, text in (files or {}).items():
            self.write_text(path, text)

    @staticmethod
    def _norm(path: str) -> str:
        return posixpath.normpath("/" + path.lstrip("/")) if path else "/"

    def _add_dir(self, path: str) -> None:
        while path not in self._dirs:
            self._dirs.add(path)
            path = posixpath.dirname(path)

    def list_dir(self, path: str) -> list[Entry]:
        path = self._norm(path)
        if path not in self._dirs:
            raise FileNotFoundError(f"No such directory: {path}")
        entries = [
            Entry(posixpath.basename(d), d, True)
            for d in self._dirs if d != path and posixpath.dirname(d) == path
        ]
        entries += [
            Entry(posixpath.basename(f), f, False, len(text.encode()))
            for f, text in self._files.items() if posixpath.dirname(f) == path
        ]
        return sort_entries(entries)

    def read_text(self, path: str) -> str:
        path = self._norm(path)
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        text = self._files[path]
        if "\x00" in text:
            raise BinaryFileError(path)
        return text

    def write_text(self, path: str, text: str) -> None:
        path = self._norm(path)
        if path in self._dirs:
            raise IsADirectoryError(path)
        self._add_dir(posixpath.dirname(path))
        self._files[path] = text

    def exists(self, path: str) -> bool:
        path = self._norm(path)
        return path in self._files or path in self._dirs

    def is_dir(self, path: str) -> bool:
        return self._norm(path) in self._dirs

    def make_dir(self, path: str) -> None:
        path = self._norm(path)
        if self.exists(path):
            raise FileExistsError(path)
        self._add_dir(path)

    def resolve(self, path: str, base: str) -> str:
        return self._norm(posixpath.join(base, path))

    def parent(self, path: str) -> str:
        return posixpath.dirname(self._norm(path))

    def join(self, directory: str, name: str) -> str:
        return self._norm(posixpath.join(directory, name))
