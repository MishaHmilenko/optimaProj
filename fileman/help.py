"""The help screen, built as a structured-text document.

Reuses the text system from the first module: DocumentBuilder creates a
heading per mode and the key list comes straight from each mode's key
map (its Command objects), so the help can never fall out of date with
the actual bindings. The rendered document is shown in a ViewerMode.
"""

from __future__ import annotations

from cli.framework import Command
from core.text import DocumentBuilder, Root

from .modes.base import Mode


def build_help(sections: list[tuple[str, Mode]], command_line: list[Command]) -> Root:
    doc = DocumentBuilder().heading("FileMan - keyboard reference")
    doc.paragraph("Keys depend on the current mode.\n"
                  "Leaving the editor with unsaved changes always asks first.")
    for title, mode in sections:
        doc.heading(title, 2).paragraph("\n".join(mode.help_lines())).end()
    doc.heading("Command line (press : in the file list)", 2)
    doc.paragraph("\n".join(f"  {c.signature:<14} {c.description}" for c in command_line))
    doc.end()
    return doc.build()
