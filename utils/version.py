"""Utilities for working with the project version."""

from __future__ import annotations

from pathlib import Path


_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def get_version() -> str:
    """Return the current project version string.

    The version is stored in the repository root ``VERSION`` file.
    """

    try:
        version = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError("VERSION file is missing from the repository root") from exc

    if not version:
        raise RuntimeError("VERSION file is empty")

    return version


__all__ = ["get_version"]
