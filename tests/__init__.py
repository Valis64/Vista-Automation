import sys
from pathlib import Path

# Ensure the repository root is on sys.path so test modules can import
# `order_gui` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
