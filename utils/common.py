"""Helper functions shared across modules."""

from __future__ import annotations

import json
import jsonschema
import sys
from pathlib import Path
import zipfile

if getattr(sys, "frozen", False):
    APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    APP_DIR = Path(__file__).resolve().parent.parent

TEMPLATE_SETTINGS_DIR = APP_DIR / "template_settings"

LAM_COLORS = {
    "matte": "#FFA500",  # [255,165,0]
    "gloss": "#008000",  # [0,128,0]
    "softtouch": "#0000FF",  # [0,0,255]
    "uncoated": "#FF4500",  # [255,69,0]
    "nolaminate": "#FF0000",  # [255,0,0]
    "smudgeproof": "#008080",  # [0,128,128]
}


def get_laminate_color(name: str) -> str:
    """Return the hex color string for the given laminate name."""
    key = name.lower().replace(" ", "")
    return LAM_COLORS.get(key, "#000000")


def load_template_settings(code: str, *, defaults: bool = True) -> dict:
    """Return per-template settings loaded from ``template_settings``.

    When ``defaults`` is True, missing optional keys such as ``mirror`` and
    ``artworkScale`` are populated with safe defaults.
    """
    if not code:
        return {}
    path = TEMPLATE_SETTINGS_DIR / f"{code.upper()}.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        validate_template_settings(data)
        if defaults:
            data = dict(data)
            data.setdefault("mirror", False)
            data.setdefault("artworkScale", 1)
        return data
    except Exception:
        return {}


def validate_template_settings(data: dict) -> bool:
    """Validate ``data`` against ``schema.json``.

    Returns True if ``data`` is valid; otherwise raises ``ValueError`` with a
    descriptive message.
    """
    schema_path = TEMPLATE_SETTINGS_DIR / "schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"Invalid template settings: {exc.message}") from exc
    return True


def save_template_settings(code: str, data: dict) -> None:
    """Write ``data`` as JSON for the given template ``code``."""
    validate_template_settings(data)
    path = TEMPLATE_SETTINGS_DIR / f"{code.upper()}.json"
    TEMPLATE_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_template_settings(code: str, updates: dict) -> None:
    """Merge ``updates`` into existing settings for ``code`` and save.

    ``updates`` may include ``None`` values to remove keys from the settings.
    """
    data = load_template_settings(code, defaults=False)
    for key, value in updates.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    save_template_settings(code, data)


def export_template_settings(archive_path: str | Path) -> Path:
    """Write all files from ``template_settings`` to a ZIP archive.

    Returns the ``Path`` to the created archive.
    """
    dest = Path(archive_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in TEMPLATE_SETTINGS_DIR.glob("*.json"):
            zf.write(file, arcname=file.name)
    return dest


def import_template_settings(archive_path: str | Path, *, overwrite: bool = False) -> None:
    """Load template settings from ``archive_path`` into ``template_settings``.

    If ``overwrite`` is ``False`` and any file already exists, ``FileExistsError``
    is raised. Files are validated against ``schema.json`` before being
    written.
    """
    src = Path(archive_path)
    if not src.exists():
        raise FileNotFoundError(src)

    TEMPLATE_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src, "r") as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if not name.endswith(".json"):
                continue
            dest = TEMPLATE_SETTINGS_DIR / name
            if name != "schema.json" and dest.exists() and not overwrite:
                raise FileExistsError(dest)
            with zf.open(info) as f:
                data = json.load(f)
            if name != "schema.json":
                validate_template_settings(data)
            with dest.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)


def is_coffee_sleeve(template: str) -> bool:
    """Return True if the template code indicates a coffee sleeve."""
    return template.strip().upper() == "CD0434" if template else False


def is_pb001(template: str) -> bool:
    """Return True if the template code indicates PB001."""
    return template.strip().upper() == "PB001" if template else False


def is_pb005(template: str) -> bool:
    """Return True if the template code indicates PB005."""
    return template.strip().upper() == "PB005" if template else False


__all__ = [
    "LAM_COLORS",
    "get_laminate_color",
    "load_template_settings",
    "save_template_settings",
    "update_template_settings",
    "export_template_settings",
    "import_template_settings",
    "validate_template_settings",
    "is_coffee_sleeve",
    "is_pb001",
    "is_pb005",
]
