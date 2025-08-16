# Automated Print File Template Creator

This repository contains an ExtendScript script (`template_creator.jsx`) for Adobe Illustrator. The file starts with `#target illustrator`, so it must run from inside Illustrator. Combined with the bundled Python GUI, it automates placing artwork into predefined templates and exports print-ready PDFs. Order data can be loaded from a URL or local file so multiple artwork/template pairs are processed with minimal manual setup.

For a detailed setup and usage guide see [docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md).

## Feature Highlights

### Order Input & Parsing
- Load order data from a URL or local HTML/JSON file.
- Download pages with `curl` using optional login credentials.
- Automatically fill **Info**, **GlueTab**, filenames and paths by parsing `unordered_items_tbody`.
- Templates and art IDs are parsed from line items and displayed with detected paper size and laminate type.

### Workflow & GUI
- **Add Pair** steps through order items; new tabs appear after nine pairs for large orders.
- Laminate and paper selections use checkboxes with remembered defaults that you can override.
- Built-in **Chat Bot** panel uses your ChatGPT API key and animates replies.
- **History** button in the Chat Bot panel opens a dashboard summarizing past runs.
- Optional completion summary saved to a temporary folder (old entries are cleaned automatically).
- Customizable artwork/template directories and adjustable UI font size.
- Optional Art Server and Google Drive paths with connectivity indicators.
- Login details and settings persist in `settings.json` so the GUI stays ready between sessions.
- The Diagnostic panel's **Open Art Directories** button shows all folders in a grid so you can monitor them live.
- The Diagnostic panel's **Move art to art folders** button organizes orders when artwork is in the order folder itself.
- The Diagnostic mode checkbox remembers its state so you don't have to re-enable it each launch.
- The loading screen displays an estimated Actions per Minute gauge while Illustrator runs.
- During processing the loading screen shows both in-progress and completed pairs with laminate color highlights. All Illustrator progress messages appear in a right-side details pane, including the filenames of saved PDFs.
- If Illustrator is silent for over 12.5 seconds, the loading screen shows "Still working..." so you know processing continues.
- Special indicators show "Coffee Sleeve", "2up", "90°" or "180°" when certain templates require rotation or duplication.
- The loading window and main GUI now show the current template code and highlight it in pink when a custom JSON file is active.
- Flagged PDFs appear in a **Human Tasks** list on the Review tab. All generated PDFs open at once with Approve and Flag buttons centered for quick access. You can choose one or more reasons or provide custom text and each selection is saved with the item.

### Template Processing
- Automatically match templates and artwork by code and paper size.
- Artwork fields remain editable; matching runs again when you press **OK**.
- Positions artwork to the template's `Bleed` path and centers the clipping group after detecting bleed bounds.
- Adds a laminate label, updates version text and inserts delays to keep Illustrator responsive.
- Template files must include `<template>_print` and `-vp` for recognition.

### Output
- Exports both `*_lines_` and `*_flat_` PDFs for each pair.
- URLs are re-fetched automatically whenever you refresh or start processing.
- `order_data.json` includes all resolved file paths so Illustrator has everything it needs.

## Review Panel

The Review tab shows a table of all flagged PDFs so you can resolve them later. Each
row lists the item name, selected reasons and the time it was flagged. Items can be
in one of three states:

- **open** – waiting for review (highlighted in red)
- **resolved** – approved and crossed out
- **ignored** – skipped but kept for reference

Unresolved items persist in `flags.json`. They reappear in the table on the next
launch so you never lose track of pending tasks.

To manipulate flagged items programmatically, import the helpers from
`review.py`:

```python
from review import ReviewManager, FlaggedItem, FlagStatus
```

**Shortcuts**

- Double-click a row to open it in Illustrator.
- Triple-click a row to open the PDF in Acrobat.
- Right-click for a context menu with **Open**, **Resolve**, **Ignore** and
  **Clear Resolved** actions.

## Requirements

- Adobe Illustrator with ExtendScript support

## Installing Dependencies

Install the Python packages listed in `requirements.txt` before running the
program or the tests:

```bash
pip install -r requirements.txt
```

## Testing

Install the dependencies above before running the tests:

```bash
pip install -r requirements.txt
```

Then run the test suite with:

```bash
pytest
```

## Quick Start

1. Install Python 3 from [python.org](https://www.python.org/).
2. Open a command prompt in this folder and run:
 ```bash
  python run_gui.py
  ```
 The helper installs the required packages (`requests>=2.32`, `beautifulsoup4`, `openai`, `customtkinter`, `packaging`, `pygetwindow`, `PyMuPDF` and `Pillow`) and launches the CustomTkinter GUI.
3. Open the **Settings** tab and, if your order site requires authentication, fill in the login URL, username, and password. Use **Test Login** to verify the connection—the indicator turns green when logged in. The login routine now reads hidden fields from the login page so it works with most standard forms. Whenever you use **Fetch**, the app downloads the page using your logged-in session without launching a browser and parses it automatically. Your credentials are written to `settings.json` so they're pre-filled on the next run.
  You can also specify an Art Server path or Google Drive folder and press their **Login** buttons to confirm access. The same tab lets you enter your ChatGPT API key and custom API base URL for the Chat Bot panel and test them with **Login ChatGPT**. If the URL doesn't end with `/v1`, the app appends it automatically so requests reach the correct endpoint.
  The **Appearance** section lets you pick a light or dark theme for the CustomTkinter interface.

## Usage

1. Launch Illustrator.
2. Run the script via **File ▶ Scripts ▶ Other Script...** and choose `template_creator.jsx`.
3. In the dialog, choose an order HTML file or enter a URL. Clicking **Download** fetches the page with `curl` and saves it to a temporary file before refreshing the dialog.
4. Choose the directories for your artwork files and print file templates if the defaults are not correct.
5. Press **Refresh Order Data** to load the first item from the order into the first pair. Use **Add Pair** to populate the next item each time you want to process another pair. When more than nine pairs are added, a new page tab appears so you can switch between sets of pairs.
6. Review the automatically detected laminate for each pair and adjust the
   checkboxes or paper settings if needed.
7. Click **OK** to process all listed pairs. The script re-checks the order HTML and searches the chosen directories for matching artwork and templates before processing. When filenames are provided, the resulting PDFs are saved in a `print` folder one level above the artwork directory. `_lines_` and `_flat_` PDFs are created for each pair.


The script inserts delays to keep Illustrator responsive during processing.

## PRINTFILESETUP

Print file templates must follow a few conventions so the script can position
artwork and export PDFs correctly:

1. **Bleed Path** – draw the outer bleed shape with a stroke color of
   **100C&nbsp;0M&nbsp;100Y&nbsp;0K** (or name the path `Bleed`). The script
   centers pasted artwork to this path and uses it to align the clipping mask.
   If more than one path matches, the largest one is used for alignment.
2. **`template` Layer** – place cut/score lines on a layer named `template`.
   This layer remains visible for the `*_lines_` PDF and is hidden for the
   `*_flat_` PDF that the script saves.
3. **Named Text Frames** – optional text frames can be added and named
   `info`, `gluetab`, and `laminate`. When present the script fills them with
   order information, glue instructions, and the laminate label. If no
   `laminate` frame exists the label is placed near the top-right of the bleed
   bounds.
4. **Artwork Bleed Path** – source artwork files must include a path stroked
   with a spot color named **Bleed**. The underlying CMYK color may be
   **100C&nbsp;0M&nbsp;100Y&nbsp;0K** or **0C&nbsp;100M&nbsp;100Y&nbsp;0K**.
   Everything outside this path is clipped before the artwork is pasted into the
   template.

## Order HTML Format

The script expects an HTML document with:
* `unordered_proof_items_tbody` providing filenames and proofing text
* a section labeled **Glue tab data** containing the glue instructions
* `unordered_items_tbody` with tables for each item

Within each item table the first row lists the quantity, template code, and art name.
The template code is the value in the second `<td>` (e.g. `RT3713`) and the art
name is in the third `<td>` (e.g. `RT3713S - MD43FBF403`). These are used to find
matching files in the chosen directories. The proofing table supplies the PDF
filename and additional info, while the **Glue tab data** section contains glue
instructions. All arrays are aligned by the pair numbers (`#1`, `#2`, etc.).

## Development

See `template_creator.jsx` for the implementation. The top of the file explains the main workflow and utility functions used.

## Template Settings

Template-specific behaviors such as rotation or additional bleed paths are configured with JSON files in the `template_settings`
folder. This folder acts as a library of special settings for every template. Each file is named after the template code (for
example `PB001.json`) and may define the following fields:

```json
{
  "rotation": 90,
  "bleedPaths": ["bleed1", "bleed2"],
  "mirror": true,
  "artworkScale": 0.95
}
```

- **rotation** – rotates the placed artwork by the given degrees.
- **bleedPaths** – comma‑separated path names treated as bleed during export.
- **mirror** – when `true`, flips the artwork horizontally before placement.
- **artworkScale** – scales the artwork by this factor (1 leaves it unchanged).

The GUI and Illustrator script automatically apply these settings whenever a template code matches one of the JSON files. Omit
any field to use the defaults.

Use **Settings → Template Settings** in the GUI to manage these files. Clicking **Add** opens a dialog that prompts for a
template code, rotation value, bleed path list, a **Mirror** checkbox and an artwork scale. For example, entering a rotation of
`90`, bleed paths `bleed1, bleed2`, enabling **Mirror** and setting scale to `0.95` will rotate, mirror and shrink artwork when
that template is processed. Current entries include rotation settings for `RT2052`, `RT3714`, `RT3712`, `RT3056`, `RT3055`,
`TT3055`, `SL3302`, `TT3056`, `TT3075` and `RT3734`.

Use the **Export** and **Import** buttons in that dialog to back up the entire
`template_settings` folder to a ZIP archive or restore from one. Importing will
prompt for confirmation before overwriting existing files.

## License

This repository is provided without a specific license. See `AGENTS.md` for project information.

## Building the Stand-Alone GUI

Use PyInstaller to create an executable for the Tkinter-based GUI:

```bash
# On Windows
pyinstaller --onefile --add-data "template_creator.jsx;." order_gui.py
# On Linux/macOS
pyinstaller --onefile --add-data "template_creator.jsx:." order_gui.py
```

Alternatively run the helper script:

```bash
python build_installer.py
```

The helper script installs PyInstaller for your user account if it's missing
(`pip install --user pyinstaller`), so administrator privileges are usually not
required.

Set `ILLUSTRATOR_EXE` to override the Illustrator path. When you run
Illustrator, both `order_data.json` and the downloaded page (HTML or JSON) are saved
alongside the bundled `template_creator.jsx`. When packaged with
PyInstaller, these files are written to the temporary extraction
directory (accessible via `sys._MEIPASS`), so the JSX script always
loads the fresh data.
Because the extraction directory is removed when the launcher exits,
the GUI hides while Illustrator runs and reappears afterward so you can continue working without restarting.

The GUI supports multi-item orders. Use **Next** and **Prev** to review
each item individually, or switch to the **Checklist** tab to see all
pairs with checkboxes. Only checked pairs are written to `order_data.json`
and processed when you click **Run Illustrator**. You can also click
**Save JSON** to export the data without launching Illustrator. The
**Settings** tab stores your Illustrator path and optional login
credentials for sites that require authentication. The login indicator
shows green when the session is active and red otherwise. Before every
fetch, the app attempts to log in using these credentials and will
include any hidden fields from the login form automatically.
If login fails, the server response is saved to `login_response.html`
alongside the executable to aid troubleshooting.
