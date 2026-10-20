"""File validation helpers used by upload routes."""

from __future__ import annotations

from pathlib import Path


def has_allowed_extension(filename: str, allowed_extensions: set[str]) -> bool:
    """Return whether a filename has one of the configured extensions."""
    return (
        "." in filename
        and Path(filename).suffix.lower().lstrip(".") in allowed_extensions
    )
