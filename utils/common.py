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
BLEED_FAILSAFE_FILE = TEMPLATE_SETTINGS_DIR / "BleedFailSafeSettings.json"
DEFAULT_BLEED_FAILSAFE_SETTINGS = {"defaultRotation": 0, "templates": {}}

ALLOWED_ALIGNMENTS = [
    "top-left",
    "top-center",
    "top-right",
    "center-left",
    "center",
    "center-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]

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


def _load_schema() -> dict:
    schema_path = TEMPLATE_SETTINGS_DIR / "schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
        for key, caster in (("rotation", int), ("artworkScale", float)):
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = caster(data[key])
                except ValueError:
                    pass
        if "alignment" in data:
            alignment = data["alignment"]
            if isinstance(alignment, str):
                normalized = alignment.strip().lower().replace("_", "-").replace(" ", "-")
                if normalized not in ALLOWED_ALIGNMENTS:
                    raise ValueError(
                        "Invalid template settings: alignment must be one of "
                        + ", ".join(ALLOWED_ALIGNMENTS)
                    )
                data["alignment"] = normalized
            else:
                raise ValueError("Invalid template settings: alignment must be a string")
        validate_template_settings(data)
        if defaults:
            data = dict(data)
            data.setdefault("mirror", False)
            data.setdefault("artworkScale", 1)
            data.setdefault("alignment", "center")
        return data
    except Exception:
        return {}


def validate_template_settings(data: dict) -> bool:
    """Validate ``data`` against ``schema.json``.

    Returns True if ``data`` is valid; otherwise raises ``ValueError`` with a
    descriptive message.
    """
    schema = _load_schema()
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


def _parse_rotation(value: object, fallback: float | int | None = None) -> float | int | None:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            val = float(value)
            return int(val) if val.is_integer() else val
        except ValueError:
            return fallback
    return fallback


def _normalize_failsafe_template_entry(entry: object, code: str) -> dict:
    normalized: dict[str, object] = {}
    rotation = _parse_rotation(entry, fallback=None)
    if isinstance(entry, dict):
        normalized.update(entry)
        rotation = _parse_rotation(entry.get("rotation"), fallback=rotation)
    if rotation is not None:
        normalized["rotation"] = rotation
    if code:
        normalized.setdefault("templateCode", code)
    die_name = normalized.get("dieName")
    if isinstance(die_name, str) and die_name.strip():
        normalized["dieName"] = die_name.strip()
    elif code:
        normalized["dieName"] = code
    return normalized


def normalize_bleed_failsafe_settings(data: dict | None, *, defaults: bool = True) -> dict:
    if not isinstance(data, dict):
        data = {}
    normalized: dict[str, object] = {}
    default_rotation = _parse_rotation(
        data.get("defaultRotation", data.get("rotation")),
        fallback=0 if defaults else None,
    )
    if default_rotation is not None:
        normalized["defaultRotation"] = default_rotation

    templates: dict[str, dict] = {}
    raw_templates = data.get("templates")
    if isinstance(raw_templates, list):
        for entry in raw_templates:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get("templateCode") or entry.get("dieName") or "").strip().upper()
            if not code:
                continue
            templates[code] = _normalize_failsafe_template_entry(entry, code)
    elif isinstance(raw_templates, dict):
        for code, entry in raw_templates.items():
            code_str = str(code).strip().upper()
            if not code_str:
                continue
            templates[code_str] = _normalize_failsafe_template_entry(entry, code_str)
    normalized["templates"] = templates

    if defaults:
        normalized.setdefault("defaultRotation", 0)
        normalized.setdefault("templates", {})
    return normalized


def validate_bleed_failsafe_settings(data: dict) -> bool:
    """Validate bleed fail-safe settings using the schema section."""

    schema = _load_schema().get("BleedFailSafeSettings")
    if not schema:
        raise FileNotFoundError("Bleed fail-safe schema not found")
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"Invalid bleed fail-safe settings: {exc.message}") from exc
    return True


def load_bleed_failsafe_settings(*, defaults: bool = True) -> dict:
    """Load fail-safe settings for bleed recreation."""
    fallback = normalize_bleed_failsafe_settings(
        DEFAULT_BLEED_FAILSAFE_SETTINGS, defaults=True
    )

    if not BLEED_FAILSAFE_FILE.exists():
        return fallback if defaults else {}
    try:
        with BLEED_FAILSAFE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = normalize_bleed_failsafe_settings(data, defaults=defaults)
        validate_bleed_failsafe_settings(normalized)
        return normalized
    except Exception:
        return fallback if defaults else {}


def save_bleed_failsafe_settings(data: dict) -> None:
    """Persist normalized bleed fail-safe settings."""

    normalized = normalize_bleed_failsafe_settings(data, defaults=True)
    validate_bleed_failsafe_settings(normalized)
    TEMPLATE_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with BLEED_FAILSAFE_FILE.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


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
            if file.name == "schema.json":
                continue
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
            if name == "schema.json":
                continue
            dest = TEMPLATE_SETTINGS_DIR / name
            if dest.exists() and not overwrite:
                raise FileExistsError(dest)
            with zf.open(info) as f:
                data = json.load(f)
            if name == "BleedFailSafeSettings.json":
                normalized = normalize_bleed_failsafe_settings(data, defaults=True)
                validate_bleed_failsafe_settings(normalized)
                payload = normalized
            else:
                validate_template_settings(data)
                payload = data
            with dest.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)


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
    "ALLOWED_ALIGNMENTS",
    "LAM_COLORS",
    "get_laminate_color",
    "load_bleed_failsafe_settings",
    "save_bleed_failsafe_settings",
    "validate_bleed_failsafe_settings",
    "normalize_bleed_failsafe_settings",
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
