#!/usr/bin/env python3
"""Build the stand-alone GUI using PyInstaller."""
import os
import subprocess
import sys
import shutil
from pathlib import Path

from utils.deps import ensure_reqs


def ensure_pyinstaller():
    """Install PyInstaller if it's not already available."""
    if shutil.which("pyinstaller") is None:
        print("PyInstaller not found. Attempting to install...")
        try:
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                "--user",
                "pyinstaller",
            ])
            if shutil.which("pyinstaller") is None:
                user_base = subprocess.check_output(
                    [sys.executable, "-m", "site", "--user-base"],
                    text=True,
                ).strip()
                script_dir = "Scripts" if os.name == "nt" else "bin"
                os.environ["PATH"] += os.pathsep + str(Path(user_base) / script_dir)
        except subprocess.CalledProcessError:
            print("Failed to install PyInstaller. Please install it manually.")
            sys.exit(1)


def build():
    base_cmd = ["pyinstaller", "--onefile"]
    add_data = "template_creator.jsx;." if os.name == "nt" else "template_creator.jsx:."
    base_cmd.extend(["--add-data", add_data, "order_gui.py"])
    subprocess.check_call(base_cmd)


def main():
    ensure_pyinstaller()
    ensure_reqs()
    build()
    dist_dir = Path("dist")
    if dist_dir.exists():
        print(f"Executable created in {dist_dir.resolve()}")


if __name__ == "__main__":
    main()
