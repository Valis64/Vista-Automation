"""Helper functions shared across modules."""

from __future__ import annotations

import json
import jsonschema
import sys
from pathlib import Path

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


def load_template_settings(code: str) -> dict:
    """Return per-template settings loaded from ``template_settings``."""
    if not code:
        return {}
    path = TEMPLATE_SETTINGS_DIR / f"{code.upper()}.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
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
    "validate_template_settings",
    "is_coffee_sleeve",
    "is_pb001",
    "is_pb005",
]
