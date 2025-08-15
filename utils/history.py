"""Helpers for storing and summarizing run history."""

from __future__ import annotations


import json
import os
import sys
import time
import traceback
from pathlib import Path
from review import FlaggedItem, save_flags

# Determine application root directory similar to order_gui
if getattr(sys, "frozen", False):
    APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    # utils directory is inside the main package; go one level up
    APP_DIR = Path(__file__).resolve().parent.parent

SUMMARY_DIR = APP_DIR / "temp" / "summary"
HISTORY_FILE = SUMMARY_DIR / "run_history.json"
FLAGS_FILE = APP_DIR / "flags.json"




def load_run_history(path: str | os.PathLike = HISTORY_FILE) -> list[dict]:
    """Return a list of previous run records."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        traceback.print_exc()
    return []




def save_run_history(hist: list[dict], path: str | os.PathLike = HISTORY_FILE) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with p.open("w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception:
        traceback.print_exc()


def record_run_history(
    duration: float,
    flagged: list[FlaggedItem] | None = None,
    path: str | os.PathLike = HISTORY_FILE,
) -> None:
    """Append a run record to the history log."""
    hist = load_run_history(path)
    hist.append({
        "timestamp": time.time(),
        "duration": duration,
        "flagged": [f.to_dict() for f in flagged] if flagged else [],
    })
    save_run_history(hist, path)


def update_last_run_flagged(
    flagged: list[FlaggedItem],
    path: str | os.PathLike = HISTORY_FILE,
) -> None:
    """Update the most recent run with flagged file info."""
    hist = load_run_history(path)
    if hist:
        hist[-1]["flagged"] = [f.to_dict() for f in flagged]
        save_run_history(hist, path)
    save_flags(flagged)


def summarize_history(path: str | os.PathLike = HISTORY_FILE) -> str:
    """Return a short text summary of recorded runs."""
    hist = load_run_history(path)
    if not hist:
        return "No history available."
    total_runs = len(hist)
    total_dur = sum(r.get("duration", 0) for r in hist)
    avg_dur = total_dur / total_runs if total_runs else 0
    flagged_total = sum(len(r.get("flagged", [])) for r in hist)
    return (
        f"Runs: {total_runs}\n"
        f"Avg duration: {avg_dur:.1f}s\n"
        f"Flagged PDFs: {flagged_total}"
    )
