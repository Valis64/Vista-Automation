#!/usr/bin/env python3
"""Pre-commit helper that bumps the VERSION file when source files change."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
SOURCE_EXTENSIONS = {".py", ".jsx"}


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ("git",) + args,
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def _get_staged_files() -> set[Path]:
    output = _run_git("diff", "--cached", "--name-only")
    files = {Path(line.strip()) for line in output.splitlines() if line.strip()}
    return files


def _parse_version(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {version!r}")
    return tuple(int(part) for part in match.groups())


def _format_version(parts: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in parts)


def _read_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:  # pragma: no cover - fails fast during hook execution
        raise SystemExit("VERSION file is missing; cannot bump version") from exc


def _write_version(version: str) -> None:
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")


def _stage_version_file() -> None:
    subprocess.run(("git", "add", "VERSION"), cwd=REPO_ROOT, check=True)


def _has_source_changes(staged_files: set[Path]) -> bool:
    for path in staged_files:
        if path.suffix in SOURCE_EXTENSIONS and path.name != "VERSION":
            return True
    return False


def main() -> int:
    staged_files = _get_staged_files()

    # If the version is already staged, assume the developer managed it manually.
    if Path("VERSION") in staged_files:
        return 0

    if not _has_source_changes(staged_files):
        return 0

    current_version = _read_version()
    major, minor, patch = _parse_version(current_version)
    new_version = _format_version((major, minor, patch + 1))

    _write_version(new_version)
    _stage_version_file()
    print(f"Bumped version: {current_version} -> {new_version}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
