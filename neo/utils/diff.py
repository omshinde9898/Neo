"""Diff utilities for Neo."""

from __future__ import annotations

import difflib
from pathlib import Path


def generate_diff(
    original: str,
    modified: str,
    fromfile: str = "original",
    tofile: str = "modified",
) -> str:
    """Generate unified diff between two strings.

    Args:
        original: Original content
        modified: Modified content
        fromfile: Label for original file
        tofile: Label for modified file

    Returns:
        Unified diff string
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    # Ensure lines end with newline for proper diff
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if modified_lines and not modified_lines[-1].endswith("\n"):
        modified_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{fromfile}",
        tofile=f"b/{tofile}",
    )

    return "".join(diff)


def preview_file_edit(
    file_path: Path,
    old_string: str,
    new_string: str,
) -> str | None:
    """Preview what an edit would look like.

    Args:
        file_path: Path to the file
        old_string: Text to replace
        new_string: Text to replace with

    Returns:
        Diff string or None if old_string not found
    """
    if not file_path.exists():
        return None

    original = file_path.read_text(encoding="utf-8", errors="replace")

    if old_string not in original:
        return None

    modified = original.replace(old_string, new_string, 1)

    return generate_diff(
        original,
        modified,
        fromfile=str(file_path.name),
        tofile=str(file_path.name),
    )
