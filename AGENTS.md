# Project Information

This repository contains scripts and utilities for generating print-ready files using Adobe Illustrator. It includes:

- **template_creator.jsx** – an ExtendScript script for Illustrator that automates placing artwork into templates and exporting PDFs.
- **order_gui.py** – a Tkinter-based GUI that downloads order data, matches artwork to templates and launches Illustrator with the correct settings.
- A suite of unit tests under `tests/` to validate the helper functions used by the GUI and processing pipeline.

No license is provided. Please refer to the README for setup and usage instructions.

## Versioning Policy
- The project version is tracked in the root-level `VERSION` file using semantic versioning (`MAJOR.MINOR.PATCH`).
- Any change to Python or JSX source files must bump the patch version. A pre-commit hook is configured to do this automatically.
- Ensure the `VERSION` file is staged and committed with every change.
- Run `pre-commit install` after cloning so the automatic version bump runs on commits.
