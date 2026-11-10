"""Exceptional states of the application.

The normal states (browsing, viewing, editing) form the state graph;
anything outside it - a file that can't be read, a path that doesn't
exist - is raised as an exception. The app catches FileManagerError and
OSError in one place (FileManagerApp.handle_key), shows the message in
the status bar and stays in the current state.
"""


class FileManagerError(Exception):
    """A user-facing error with a readable message."""


class BinaryFileError(FileManagerError):
    def __init__(self, path: str) -> None:
        super().__init__(f"{path} is not a text file")


class FileTooLargeError(FileManagerError):
    def __init__(self, path: str, limit: int) -> None:
        super().__init__(f"{path} is larger than {limit // 1024} KB")
