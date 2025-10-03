"""Dependency management helpers."""

import subprocess
import sys

# Packages required by the GUI. These need to be installed before running
# PyInstaller so they're bundled with the executable.
REQS = [
    "requests>=2.32",
    "beautifulsoup4",
    "openai",
    "customtkinter",
    "packaging",
    "pygetwindow",
    "PyMuPDF",
    "Pillow",
]


def ensure_reqs():
    """Install runtime requirements if missing."""
    missing = []
    for pkg in REQS:
        mod = pkg.split("==")[0].split(">=")[0]
        mod_name = {"beautifulsoup4": "bs4"}.get(mod, mod)
        try:
            module = __import__(mod_name)
        except ImportError:
            missing.append(pkg)
            continue
        except NotImplementedError:
            continue
        if ">=" in pkg:
            req_version = pkg.split(">=")[1]
            have = getattr(module, "__version__", "0")
            try:
                from packaging.version import parse as vparse
                if vparse(have) < vparse(req_version):
                    missing.append(pkg)
            except Exception:
                pass
    if missing:
        print("Installing missing packages:", ", ".join(missing))
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            *missing,
        ])

