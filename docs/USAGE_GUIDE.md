# Full Setup and Usage Guide

This document explains how to configure and run the automated template processing tool.
It expands on the information in the main README and is designed for training a custom
GPT helper.

## 1. Installation

1. Ensure **Python 3** is installed.
2. Clone the repository and open a terminal in the project directory.
3. Install the requirements:

   ```bash
   pip install -r requirements.txt
   ```

   This installs **requests**, **beautifulsoup4**, **openai**, **customtkinter**, **packaging**, **pygetwindow**, **PyMuPDF** and **Pillow**.
4. Optional: create a virtual environment to isolate dependencies.

## 2. Launching the GUI

Run the helper script which installs dependencies (if missing) and starts the Tkinter GUI:

```bash
python run_gui.py
```

If you prefer to run the GUI module directly, ensure the requirements are installed and use:

```bash
python order_gui.py
```

## 3. Initial Configuration

1. Open the **Settings** tab.
2. Set the path to *Adobe Illustrator* if the default does not match your system. You can browse for the executable using **Browse Illustrator**.
3. If your order site requires authentication, enter the login URL, username and password, then click **Test Login**. A green indicator confirms success. Hidden form fields are detected automatically.
4. Optionally specify paths for an **Art Server** and **Google Drive**. Use the respective **Login** buttons to verify connectivity. Status messages appear in the log panel.
5. Provide your **ChatGPT API key** (and optionally a custom API URL) to enable the built-in chat panel. Choose **Login ChatGPT** to verify connection. The URL should end with `/v1` (the program appends it if needed).
6. Select a GUI theme from the **Appearance** section. Choices are *System*, *Light* and *Dark*.
6. Save your settings—they are stored in `settings.json` for next time.

## 4. Fetching Order Data

There are two ways to supply order information:

1. **URL Fetch** – enter the order page URL and press **Fetch**. If login credentials are configured, the page is downloaded using your authenticated session. The HTML is saved to `order.html`.
2. **Load File** – choose a local HTML or JSON file containing order data.

The program parses the file for items and automatically fills fields such as filenames, laminate options and template codes.

## 5. Preparing Item Pairs

- Each order item forms a *pair* consisting of the artwork file and its matching template.
- Use **Add Pair** to insert additional pairs. New tabs appear when you exceed nine pairs.
- Fields for **GlueTab**, **Info** and filenames are populated from the order data but remain editable.
- Laminate and paper selections use checkboxes so you can override the automatic detection.
- The checklist tab lists all pairs with checkboxes so you can enable or disable them before processing.

## 6. Running Illustrator

1. Review all pairs and ensure the correct directories are selected for artwork and templates.
2. Click **Run Illustrator**. The GUI hides while Illustrator runs the script `template_creator.jsx` with the generated `order_data.json`.
3. Progress messages stream in the log window along with a running step count.
4. When finished, the GUI reappears. If **Show Summary** is enabled, a summary dialog displays briefly and saves to the `temp/summary` directory.

Exported PDF files are written to a `print` folder relative to the artwork directory, creating `_lines_` and `_flat_` versions for each pair.

## 7. Building a Stand-Alone Executable

To create a single-file GUI application using PyInstaller, run:

```bash
python build_installer.py
```

This installs PyInstaller for your user account if necessary and bundles `order_gui.py` and `template_creator.jsx` together. When running from the bundle, data files are extracted to a temporary directory so Illustrator always processes fresh inputs.

## 8. Template and Artwork Guidelines

For accurate placement and PDF export, templates and artwork should follow these rules:

1. **Bleed Path** – the template must include a path stroked `100C 0M 100Y 0K` or named `Bleed`. Artwork is centered to this path.
2. **`template` Layer** – place cut/score lines on a layer named `template`. It remains visible for `_lines_` PDFs and hidden for `_flat_` PDFs.
3. **Optional Frames** – text frames named `info`, `gluetab` and `laminate` can be used to insert order details automatically. Otherwise the laminate label is placed near the top-right of the bleed area.
4. **Artwork Bleed Path** – source art should contain a path using a spot color named `Bleed`. Everything outside this path is clipped before pasting into the template.

## 9. Order HTML Structure

The parser expects an HTML document containing the following sections:

- `unordered_proof_items_tbody` – provides filenames and proofing information.
- `Glue tab data` – contains glue instructions for each pair.
- `unordered_items_tbody` – tables that list quantity, template code and full art name.

Pairs are aligned by index (`#1`, `#2`, etc.) so each table row corresponds to a proofing entry.

## 10. Troubleshooting Tips

- If login fails, the server response is saved to `login_response.html` alongside the program. Review this file to diagnose authentication issues.
- Connection indicators on the Settings tab show green when paths or services are accessible and red otherwise.
- Enable **Show Summary** to generate a short log of completed steps. Old summaries are cleaned automatically after 90 days.
- If a mismatch between artwork and template color profiles is detected, the script will convert the artwork unless **Preserve Color Profile** is enabled on the Settings tab.

## 11. Template Settings

Place JSON files inside `template_settings/` to define behaviors for specific templates. Each file name should match the
template code and may specify a rotation angle, additional bleed path names, whether the artwork should be mirrored, or a scale
factor override.

Example:

```json
{
  "rotation": 90,
  "mirror": true,
  "artworkScale": 0.95,
  "bleedPaths": ["bleed1", "bleed2"]
}
```

- **rotation** – rotates the artwork on the template by the given degrees.
- **bleedPaths** – additional path names to treat as bleed when exporting.
- **mirror** – flips the artwork horizontally before placement.
- **artworkScale** – scales the artwork by this factor.

Existing settings files remain valid. To migrate, simply add `mirror` or `artworkScale` only to templates that require those
overrides. The program automatically loads these files when processing a matching template.

Open the **Template Settings** dialog from the Settings tab to manage these files. The **Add** button launches a dialog asking
for the template code, rotation value, comma-separated bleed paths, a **Mirror** toggle and an artwork scale. For instance,
entering `90` for rotation, `bleed1, bleed2` for bleed paths and checking **Mirror** will rotate, include the listed paths and
flip the artwork during processing. Use the **Export** button to save all settings to a ZIP archive and **Import** to restore
them. Importing asks for confirmation before overwriting existing files.

## 12. Additional Notes

- The GUI stores the most recently used directories and credentials in `settings.json`.
- When Illustrator is launched from the GUI, both `order_data.json` and the downloaded page are written next to the script so ExtendScript has access to up-to-date data.
- The Chat Bot panel animates responses character by character, creating the effect of rapid typing. Use it for quick questions while processing orders.
- Use **Open Art Directories** in the Diagnostic panel to show all artwork folders side by side in a grid.
- Use **Move art to art folders** in the Diagnostic panel to create missing `art` folders and relocate files.
- The Diagnostic mode checkbox saves its last value so you don't need to toggle it every session.
- **Preserve Color Profile** instructs the exporter to stop if artwork and template color spaces differ instead of converting automatically.
- The loading window shows an estimated Actions per Minute gauge while processing.
- If Illustrator doesn't report progress for 12.5 seconds, the window shows "Still working..." to confirm activity.
- During processing the log labels pairs with notes like "Coffee Sleeve", the number of copies (e.g. "2up"), or rotation angles when template settings specify them.

## 13. ChatGPT Integration Ideas

- Use the existing **Chat Bot** panel in `order_gui.py`. After supplying your API key, it allows direct chat queries while you work in the application. Replies appear in real time with an animated typing effect.
- Automate order-related tasks or summarization through additional OpenAI calls. The `utils/history.py` module, for instance, provides run history summaries; you could expand it to generate AI-driven summaries or reports.
- Provide contextual help for templates or order processing, using ChatGPT to answer quick questions or troubleshoot steps directly within the app.

---

With this information your custom GPT can assist users with installation, configuration and daily operation of the program.
