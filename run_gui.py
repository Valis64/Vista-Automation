#!/usr/bin/env python3
"""Install requirements and launch the GUI."""
import runpy
import sys
import os
from pathlib import Path

from utils.deps import ensure_reqs


def main():
    ensure_reqs()
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        print("Error: DISPLAY environment variable not set; cannot open GUI.")
        return
    gui = Path(__file__).resolve().parent / "order_gui.py"
    runpy.run_path(gui, run_name="__main__")


if __name__ == "__main__":
    main()
