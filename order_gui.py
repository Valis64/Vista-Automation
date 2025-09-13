# requirements.txt
# requests
# beautifulsoup4

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from urllib.parse import urljoin

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
import tkinter.font as tkfont
try:
    import customtkinter as ctk
except Exception:
    ctk = None
import requests
import openai
from bs4 import BeautifulSoup
import re
import tempfile
import time
import threading
import math
import shutil
from loading_window import LoadingWindow
from utils.common import (
    LAM_COLORS,
    get_laminate_color,
    load_template_settings,
    save_template_settings,
    update_template_settings,
    export_template_settings,
    import_template_settings,
    is_coffee_sleeve,
    is_pb001,
    is_pb005,
)
from utils.history import (
    load_run_history,
    save_run_history,
    record_run_history,
    update_last_run_flagged,
    summarize_history,
)
from review import (
    FlaggedItem,
    FlagStatus,
    load_flags,
    save_flags,
    ReviewManager,
    FLAG_REASONS,
)
try:
    import pygetwindow as gw
except Exception:
    gw = None


if getattr(sys, "frozen", False):
    # PyInstaller extracts files to a temp folder stored in _MEIPASS
    APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    APP_DIR = Path(__file__).resolve().parent
ILLUSTRATOR_EXE = os.getenv(
    "ILLUSTRATOR_EXE",
    r"C:\\Program Files\\Adobe\\Adobe Illustrator 2025\\Support Files\\Contents\\Windows\\ILLUSTRATOR.EXE",
)
JSX_FILE = "template_creator.jsx"
DONE_FILE = "jsx_done.flag"
PROGRESS_FILE = "jsx_progress.txt"
PAUSE_FILE = "jsx_pause.flag"
CANCEL_FILE = "jsx_cancel.flag"

SUMMARY_DIR = APP_DIR / "temp" / "summary"
PAPER_SUMMARY_DIR = APP_DIR / "temp" / "paper types summary"


def ensure_summary_dir():
    """Create summary directory and remove files older than 90 days."""
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 90 * 24 * 3600
    for f in SUMMARY_DIR.glob("*"):
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
        except Exception:
            pass

def ensure_paper_summary_dir():
    """Create paper types summary directory and purge old files."""
    PAPER_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 90 * 24 * 3600
    for f in PAPER_SUMMARY_DIR.glob("*"):
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
        except Exception:
            pass


SETTINGS_FILE = "settings.json"
TEMPLATE_SETTINGS_DIR = APP_DIR / "template_settings"

# Base URL used when fetching an order by its number
ORDER_BASE_URL = "https://www.yourboxsolution.com/admin/order-details.html?id="

# Placeholder URL for the work queue used to gather order numbers. The actual
# domain is provided via the Settings dialog so the code can remain generic.
QUEUE_PAGE_URL = ""

# Default ChatGPT API base URL
CHAT_API_URL = "https://api.openai.com/v1"



def get_queue_headers(referer: str | None = None) -> dict[str, str]:
    """Return browser-like headers for queue requests."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
            "Gecko/20100101 Firefox/123.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if referer:
        headers["Referer"] = referer
    return headers

def load_settings() -> dict:
    path = APP_DIR / SETTINGS_FILE
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            traceback.print_exc()
    return {}


def save_settings(data: dict):
    path = APP_DIR / SETTINGS_FILE
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        traceback.print_exc()


def detect_laminate(text: str) -> str:
    if not text:
        return ""
    t = text.lower().replace(" ", "")
    options = [
        "matte",
        "gloss",
        "softtouch",
        "uncoated",
        "nolaminate",
        "smudgeproof",
    ]
    for opt in options:
        if opt in t:
            return opt.title().replace("nolaminate", "No Laminate").replace("smudgeproof", "Smudge Proof")
    return ""


def detect_emboss(text: str) -> bool:
    """Return True if embossing is mentioned in the given HTML/text."""
    return bool(re.search(r"emboss", text, re.I))


def extract_art_id(text: str) -> str:
    """Return a 10-character art code from ``text`` if present."""

    if not text:
        return ""

    # Break apart by common separators so tokens like ``NAME_CODE_EXTRA`` are
    # handled in addition to ``NAME - CODE - EXTRA``.
    tokens = re.split(r"[\s_-]+", text.strip())
    for idx, t in enumerate(tokens):
        if re.fullmatch(r"[A-Z0-9]{10}", t, re.I):
            if idx == 0 and len(tokens) > 1:
                continue
            return t

    # Fallback: grab the first 10-character alphanumeric sequence anywhere in
    # the string so even unusual formats still yield something sensible.
    m = re.search(r"[A-Z0-9]{10}", text, re.I)
    return m.group(0) if m else ""


def parse_order(html: str) -> dict:
    """Parse order HTML using regex patterns matching the JSX implementation.

    Returns a dictionary with keys:
    - ``items``: list of order item dictionaries as before
    - ``pairs``: list of ``{"template": str, "art_id": str}`` extracted from
      ``div.order-items`` blocks
    - ``order_info``: dictionary with ``order_id``, ``created_by``,
      ``ordered_by`` and ``company`` if found in the HTML
    """
    text = re.sub(r"\r?\n", " ", html)

    filenames: list[str] = []
    infos: list[str] = []
    art_names: list[str] = []
    template_names: list[str] = []
    lam_types: list[str] = []
    pairs: list[dict] = []

    proof = re.search(r"<tbody[^>]*id=['\"]unordered_proof_items_tbody['\"][^>]*>([\s\S]*?)</tbody>", text, re.I)
    if proof:
        row_regex = re.compile(r"<tr[^>]*>[\s\S]*?<span[^>]*class=['\"]fl_name['\"][^>]*>(.*?)</span>[\s\S]*?<span[^>]*class=['\"]font-11['\"][^>]*>(.*?)</span>", re.I)
        for row in row_regex.finditer(proof.group(1)):
            fname = re.sub(r"<[^>]+>", "", row.group(1) or "").strip()
            info_text = row.group(2) or ""
            info_text = re.sub(r"<br\s*/?>", " ", info_text)
            info_text = re.sub(r"<[^>]+>", "", info_text)
            info_text = re.sub(r"\s+", " ", info_text).strip()
            if fname:
                filenames.append(fname)
            if info_text:
                infos.append(info_text)

    glues: list[str] = []
    glue_regex = re.compile(r"<strong>\s*Glue tab data\s*</strong>[\s\S]*?</tr>([\s\S]*?)</tbody>", re.I)
    for gm in glue_regex.finditer(text):
        td_block = gm.group(1)
        td_regex = re.compile(r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.I)
        for t in td_regex.finditer(td_block):
            val = re.sub(r"<[^>]+>", "", t.group(1)).strip()
            if val:
                glues.append(val)

    item_block = re.search(r"<tbody[^>]*id=['\"]unordered_items_tbody['\"][^>]*>([\s\S]*?)</tbody>", text, re.I)
    if item_block:
        tbl_regex = re.compile(r"<table[^>]*table-inside[^>]*>([\s\S]*?)</table>", re.I)
        for tbl in tbl_regex.finditer(item_block.group(1)):
            chunk = tbl.group(1)
            row_match = re.search(r"<tr[^>]*>\s*<td[^>]*><strong>\d+</strong></td>\s*<td[^>]*><strong>([^<]+)</strong></td>\s*<td[^>]*><strong>([^<]+)</strong>", chunk, re.I)
            temp_match = row_match.group(1) if row_match else ""
            lam_match = re.search(r"<span[^>]*style=['\"][^>]*>([^<]+)</span>", chunk, re.I)
            fl_match = re.search(r"<span[^>]*class=['\"]fl_name['\"][^>]*>([^<]+)</span>", chunk, re.I)
            a = fl_match.group(1) if fl_match else ""
            lam_text = lam_match.group(1) if lam_match else ""
            a = re.sub(r"<[^>]+>", "", a).strip()
            tcode = re.sub(r"<[^>]+>", "", temp_match).strip()
            lam_text = re.sub(r"<[^>]+>", "", lam_text).strip()
            if a:
                art_names.append(a)
            if tcode:
                template_names.append(tcode)
            lam_types.append(detect_laminate(lam_text))

    count = max(
        len(filenames),
        len(infos),
        len(glues),
        len(art_names),
        len(template_names),
        len(lam_types),
    )
    items: list[dict] = []
    for i in range(count):
        items.append(
            {
                "filename": filenames[i] if i < len(filenames) else "",
                "info": infos[i] if i < len(infos) else "",
                "gluetab": glues[i] if i < len(glues) else "",
                "artName": art_names[i] if i < len(art_names) else "",
                "templateName": template_names[i]
                if i < len(template_names)
                else "",
                "lamType": lam_types[i] if i < len(lam_types) else "",
            }
        )

    soup = BeautifulSoup(html, "html.parser")

    # Preferred simple structure
    for div in soup.select("div.order-items div.item"):
        t = div.find("span", class_="template")
        a_full = div.find("span", class_="art-full")
        if not (t and a_full):
            continue
        template = t.get_text(strip=True)
        art_full = a_full.get_text(strip=True)
        art_id = extract_art_id(art_full)
        pairs.append({"template": template, "art_id": art_id})

    # Fallback for complex table layout
    if not pairs:
        for tbl in soup.select("tbody#unordered_items_tbody table.table-inside"):
            first_row = tbl.find("tr")
            if not first_row:
                continue
            cells = first_row.find_all("td")
            if len(cells) < 3:
                continue
            template = cells[1].get_text(strip=True)
            art_full = cells[2].get_text(strip=True)
            art_id = extract_art_id(art_full)
            if template or art_id:
                pairs.append({"template": template, "art_id": art_id})

    # Order details
    def _extract(regex: str) -> str:
        m = re.search(regex, text, re.I)
        if not m:
            return ""
        val = m.group(1).strip()
        val = re.sub(r"\s*\(.*", "", val)
        return val

    order_info = {
        "order_id": _extract(r"<strong>\s*Order ID:\s*</strong>\s*(\d+)") or "",
        "created_by": _extract(r"<strong>\s*Created By:\s*</strong>\s*([^<(]*)"),
        "ordered_by": _extract(r"<strong>\s*Ordered By:\s*</strong>\s*([^<(]*)"),
        "company": _extract(r"<strong>\s*Company:\s*</strong>\s*([^<]+)"),
    }

    return {"items": items, "pairs": pairs, "order_info": order_info}


def parse_order_json(text: str) -> dict:
    obj = json.loads(text)
    if isinstance(obj, dict) and "items" in obj:
        return {
            "items": obj["items"],
            "pairs": obj.get("pairs", []),
            "art_dir": obj.get("art_dir", ""),
            "template_dir": obj.get("template_dir", ""),
            "month_dir": obj.get("month_dir", ""),
            "order_id": obj.get("order_id", ""),
            "show_summary": obj.get("show_summary", False),
            "summary_dir": obj.get("summary_dir", ""),
            "order_info": obj.get("order_info", {}),
        }
    if isinstance(obj, list):
        return {
            "items": obj,
            "pairs": [],
            "art_dir": "",
            "template_dir": "",
            "show_summary": False,
            "summary_dir": "",
            "order_info": {},
        }
    raise ValueError("Unsupported JSON structure")


def save_order_data(data: dict):
    out_path = APP_DIR / "order_data.json"
    data["summary_dir"] = str(SUMMARY_DIR)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_order_html(html: str):
    out_path = APP_DIR / "order.html"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(html)

def save_temp_html(html: str) -> str:
    path = Path(tempfile.gettempdir()) / f"order_{int(time.time())}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return str(path)


def find_art_file(
    root: str,
    art_id: str,
    month_dir: str = "",
    order_id: str = "",
    name_hint: str = "",
) -> str:
    """Locate an artwork file using an ``art_id`` or optional ``name_hint``.

    If ``month_dir`` and ``order_id`` are provided, the search first checks
    ``month_dir/<order_id>/art`` before falling back to ``root``.
    """

    if not art_id and not name_hint:
        return ""

    search_dirs = []
    if month_dir and order_id:
        order_path = os.path.join(month_dir, str(order_id), "art")
        if os.path.isdir(order_path):
            search_dirs.append(order_path)
    if root:
        search_dirs.append(root)

    art_id_l = art_id.lower()
    name_hint_l = name_hint.lower()
    for sroot in search_dirs:
        for dirpath, _, files in os.walk(sroot):
            for name in files:
                if not name.lower().endswith((".ai", ".pdf")):
                    continue
                low = name.lower()
                if art_id and art_id_l in low:
                    return os.path.join(dirpath, name)
                if name_hint and name_hint_l in low:
                    return os.path.join(dirpath, name)
    return ""


def find_template_file(root: str, template: str, sample: bool = False) -> str:
    """Return the template file path for ``template``.

    When ``sample`` is ``True`` the name must contain ``(SAMPLE)``.  When
    ``False`` any such files are ignored.
    """
    if not root or not template:
        return ""
    tmpl_l = template.lower()
    candidates: list[tuple[int, str]] = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            low = name.lower()
            if (
                low.endswith((".ai", ".pdf"))
                and tmpl_l in low
                and "_print" in low
                and "-vp" in low
            ):
                if sample and "(sample)" not in low:
                    continue
                if not sample and "(sample)" in low:
                    continue
                m = re.search(r"(\d+)in", low)
                num = int(m.group(1)) if m else 999
                candidates.append((num, os.path.join(dirpath, name)))
    if not candidates:
        return ""
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def cut_file_for_template(template_path: str) -> str:
    """Return the matching cut file path for ``template_path`` if it exists."""
    if not template_path:
        return ""
    base = os.path.basename(template_path)
    base = re.sub(r"_print", "_cut", base, flags=re.I)
    base = base.replace("(SAMPLE)", "").replace("(sample)", "")
    base = re.sub(r"\s+", " ", base).strip()
    base = re.sub(r"\s+\.", ".", base)
    path = os.path.join(os.path.dirname(template_path), base)
    if os.path.isfile(path):
        return path
    root, ext = os.path.splitext(path)
    alt = root + (".ai" if ext.lower() == ".pdf" else ".pdf")
    return alt if os.path.isfile(alt) else ""


def extract_paper_type(path: str) -> str:
    if not path:
        return ""
    m = re.search(r"(\d+in)", os.path.basename(path).lower())
    return m.group(1) if m else ""


def get_item_quantity(item: dict) -> int:
    """Return the quantity for an order item, or ``0`` if unknown."""
    info = str(item.get("info", ""))
    m = re.search(r"quantity[:\s-]*(\d+)", info, re.I)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    glue = str(item.get("gluetab", ""))
    m = re.search(r"-\s*\[?(\d+)\]?\s*$", glue)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return 0


def sanitize_filename_base(name: str) -> str:
    """Return ``name`` without a trailing ``lines`` segment."""
    if not name:
        return ""
    return re.sub(r'(?:_lines|\s+lines)$', '', name, flags=re.I)


def write_paper_summary(pairs: list[dict], out_dir: str | os.PathLike | None = None) -> list[str]:
    """Write a file listing paper types for each order and return paths."""
    if out_dir is None:
        out_dir = PAPER_SUMMARY_DIR
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    orders: dict[str, set[str]] = {}
    for p in pairs:
        order = str(p.get("order_id", "")).strip()
        paper = str(p.get("paperType", "")).strip()
        if order and paper:
            orders.setdefault(order, set()).add(paper)
    written: list[str] = []
    for order, papers in orders.items():
        path = out_path / f"{order}_paper_types.txt"
        try:
            with open(path, "w", encoding="utf-8") as f:
                for paper in sorted(papers):
                    f.write(paper + "\n")
            written.append(str(path))
        except Exception:
            traceback.print_exc()
    return written


def move_art_to_folder(order_dir: str) -> int:
    """Move .ai or .pdf files in ``order_dir`` to an ``art`` subfolder.

    Returns the number of files moved.
    """
    if not os.path.isdir(order_dir):
        return 0
    art_dir = os.path.join(order_dir, "art")
    if os.path.isdir(art_dir):
        return 0
    files = [f for f in os.listdir(order_dir) if f.lower().endswith((".ai", ".pdf"))]
    if not files:
        return 0
    os.makedirs(art_dir, exist_ok=True)
    moved = 0
    for name in files:
        src = os.path.join(order_dir, name)
        dest = os.path.join(art_dir, name)
        try:
            shutil.move(src, dest)
            moved += 1
        except Exception:
            traceback.print_exc()
    return moved


def parse_queue(html: str) -> list[str]:
    """Extract order numbers for the company 'Vista' from a queue page."""
    soup = BeautifulSoup(html, "html.parser")
    order_ids: list[str] = []
    for row in soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        if len(cells) >= 4:
            num_cell, company_cell = cells[1], cells[3]
        else:
            num_cell, company_cell = cells[0], cells[1]
        num = re.sub(r"\D+", "", num_cell.get_text())
        company = company_cell.get_text(strip=True)
        if num and "vista" in company.lower():
            order_ids.append(num)
    return order_ids


def build_queue_url(login_url: str, page_url: str) -> str:
    """Return an absolute queue page URL."""
    return urljoin(login_url, page_url)


def parse_login_form(html: str, base_url: str, username: str, password: str) -> tuple[str, str, dict]:
    """Return (url, method, payload) for submitting a login form."""
    action_url = base_url
    method = "post"
    payload: dict[str, str] = {}
    try:
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if form:
            action_url = urljoin(base_url, form.get("action", action_url))
            method = form.get("method", "post").lower()
            for inp in form.find_all("input"):
                name = inp.get("name")
                if not name:
                    continue
                value = inp.get("value", "")
                t = inp.get("type", "text").lower()
                lname = name.lower()
                if t != "hidden" and ("user" in lname or "email" in lname or lname == "login"):
                    value = username
                elif t == "password" or "pass" in lname:
                    value = password
                payload[name] = value
    except Exception:
        traceback.print_exc()

    if not payload:
        payload = {
            "username": username,
            "email": username,
            "user": username,
            "login": username,
            "password": password,
            "pass": password,
            "pwd": password,
        }

    if "action" not in payload:
        payload["action"] = "signin"
    return action_url, method, payload





def launch_illustrator(path: str, progress_cb=None, still_interval: float = 12.5):
    done = APP_DIR / DONE_FILE
    progress = APP_DIR / PROGRESS_FILE
    pause_flag = APP_DIR / PAUSE_FILE
    cancel_flag = APP_DIR / CANCEL_FILE
    try:
        if done.exists():
            done.unlink()
    except Exception:
        pass
    try:
        if progress.exists():
            progress.unlink()
        if pause_flag.exists():
            pause_flag.unlink()
        if cancel_flag.exists():
            cancel_flag.unlink()
    except Exception:
        pass

    proc = subprocess.Popen(
        [path, os.path.join(APP_DIR, JSX_FILE)], shell=False, cwd=APP_DIR
    )

    last_mtime = None
    last_update = time.monotonic()
    while True:
        if cancel_flag.exists():
            try:
                proc.kill()
            except Exception:
                pass
            cancel_flag.unlink()
            break
        if progress_cb and progress.exists():
            try:
                mtime = progress.stat().st_mtime
                if last_mtime != mtime:
                    last_mtime = mtime
                    with progress.open("r", encoding="utf-8") as f:
                        msg = f.read().strip()
                    if msg:
                        progress_cb(msg)
                        last_update = time.monotonic()
            except Exception:
                pass
        elif progress_cb and time.monotonic() - last_update > still_interval:
            progress_cb("Still working...")
            last_update = time.monotonic()
        if done.exists():
            break
        if proc.poll() is not None:
            break
        # Poll frequently so we don't miss quick status updates like the first
        # "Processing pair" message.
        time.sleep(0.05)


def populate_pairs(
    frame: tk.Frame,
    vars_list: list,
    items: list[dict],
    pair_data: list[dict] | None = None,
    foil_vars: list[tk.BooleanVar] | None = None,
    emboss_vars: list[tk.BooleanVar] | None = None,
    emboss_default: bool = False,
):
    """Populate checklist rows showing order, art ID and production details.

    ``items`` and ``pair_data`` are expected to align by index. ``pair_data`` is
    preferred for extracting art IDs and template codes so the checklist matches
    the "Current Pair" display. ``foil_vars`` and ``emboss_vars`` optionally
    receive lists of boolean variables for the "Foil die" and "Emboss"
    checkboxes (default unchecked). ``emboss_default`` checks the emboss box for
    coffee sleeves when ``True``.
    """

    for child in frame.winfo_children():
        child.destroy()
    vars_list.clear()
    if foil_vars is not None:
        foil_vars.clear()
    if emboss_vars is not None:
        emboss_vars.clear()

    header = tk.Frame(frame)
    header.grid(row=0, column=0, sticky="w")
    for col, text in enumerate(["", "Item", "Laminate", "Foil die", "Emboss"]):
        tk.Label(header, text=text, font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=col, sticky="w", padx=2
        )
    order_counters: dict[str, int] = {}
    for idx_item, it in enumerate(items, start=1):
        oid = str(it.get("order_id", "")).strip()
        order_counters[oid] = order_counters.get(oid, 0) + 1
        seq = order_counters[oid]
        company = it.get("company", "")
        art_id = ""
        template = ""
        if pair_data and idx_item - 1 < len(pair_data):
            pair = pair_data[idx_item - 1]
            art_id = pair.get("art_id", "")
            template = pair.get("template", "")
        else:
            art_text = it.get("artName") or it.get("filename", "")
            art_id = extract_art_id(art_text)
            template = it.get("templateName", "")
        glue = it.get("gluetab", "")
        lam = it.get("lamType", "") or detect_laminate(it.get("info", ""))
        if not lam and is_coffee_sleeve(template):
            lam = "Uncoated"
        lam_color = get_laminate_color(lam)

        row = tk.Frame(frame)
        row.grid(row=idx_item, column=0, sticky="w")

        var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, variable=var).grid(row=0, column=0, sticky="w")
        text = f"{oid}.{seq} - {company} - {art_id} -> {template} <- ({glue}) - "
        tk.Label(row, text=text, anchor="w").grid(row=0, column=1, sticky="w")
        tk.Label(row, text=lam, foreground=lam_color).grid(row=0, column=2, sticky="w", padx=2)
        foil_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row, text="Foil die", variable=foil_var).grid(row=0, column=3, sticky="w", padx=2)
        emboss_checked = emboss_default and is_coffee_sleeve(template)
        emboss_var = tk.BooleanVar(value=emboss_checked)
        tk.Checkbutton(row, text="Emboss", variable=emboss_var).grid(row=0, column=4, sticky="w")

        vars_list.append(var)
        if foil_vars is not None:
            foil_vars.append(foil_var)
        if emboss_vars is not None:
            emboss_vars.append(emboss_var)

    return len(items)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        # Expose template settings editor to other windows
        root.open_template_settings_editor = self.open_template_settings_editor
        root.title("Illustrator Automation")
        try:
            fonts = [
                "TkDefaultFont",
                "TkTextFont",
                "TkFixedFont",
                "TkMenuFont",
                "TkHeadingFont",
            ]
            for name in fonts:
                f = tkfont.nametofont(name)
                f.configure(size=f.cget("size") + 2)
        except Exception:
            pass
        # Resize the window based on the available screen space
        try:
            scr_w = root.winfo_screenwidth()
            scr_h = root.winfo_screenheight()
        except Exception:
            scr_w = scr_h = 0
        width = min(1200, scr_w or 1200)
        height = min(900, scr_h or 900)
        root.geometry(f"{width}x{height}")
        ensure_summary_dir()
        ensure_paper_summary_dir()

        self.items: list[dict] = []
        self.index = 0
        self.editable = False
        self.html_content: str | None = None
        self.temp_path: str | None = None
        self.pairs: list[dict] = []
        self.batch_items: list[dict] = []
        self.batch_pairs: list[dict] = []
        self.batch_orders: list[str] = []
        self._ignore_table_event = False
        self._ignore_url_change = False
        self.missing_templates_win: tk.Toplevel | None = None
        self.missing_templates_log: scrolledtext.ScrolledText | None = None
        self.missing_cut_win: tk.Toplevel | None = None
        self.missing_cut_log: scrolledtext.ScrolledText | None = None
        self.sample_copy_info: list[tuple[str, str]] = []
        self.run_start_time: float | None = None
        self.total_time_var = tk.StringVar(value="Total time: 0s")

        container = tk.Frame(root)
        container.pack(fill="both", expand=True)

        # Chatbot panel on the left
        chat_frame = tk.LabelFrame(container, text="Chat Bot")
        chat_frame.pack(side="left", fill="y", padx=5, pady=5)
        self.chat_log = scrolledtext.ScrolledText(chat_frame, width=60, height=25, state="disabled")
        self.chat_log.pack(fill="both", expand=True)
        chat_entry = tk.Frame(chat_frame)
        chat_entry.pack(fill="x", pady=(5, 0))
        self.chat_input_var = tk.StringVar()
        chat_input = tk.Entry(chat_entry, textvariable=self.chat_input_var)
        chat_input.pack(side="left", fill="x", expand=True)
        chat_input.bind("<Return>", lambda e: (self.send_chat(), "break"))
        tk.Button(chat_entry, text="Send", command=self.send_chat).pack(side="left")
        tk.Button(chat_entry, text="History", command=self.show_dashboard).pack(side="left", padx=(5, 0))

        nb = ttk.Notebook(container)
        order_tab = ttk.Frame(nb)
        pairs_tab = ttk.Frame(nb)
        review_tab = ttk.Frame(nb)
        settings_tab = ttk.Frame(nb)
        nb.add(order_tab, text="Order")
        nb.add(pairs_tab, text="Checklist")
        nb.add(review_tab, text="Review")
        nb.add(settings_tab, text="Settings")
        nb.pack(side="left", fill="both", expand=True)
        self.nb = nb
        self.settings_tab = settings_tab
        self.review_tab = review_tab

        # Review tab contents
        tk.Label(review_tab, text="Human Tasks").pack(anchor="w", padx=5)
        tree_frame = tk.Frame(review_tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        cols = ("item", "reasons", "timestamp", "status")
        self.task_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            selectmode="extended",
            style="Review.Treeview",
        )
        headings = ["Item", "Reasons", "Timestamp", "Status"]
        for c, h in zip(cols, headings):
            self.task_tree.heading(c, text=h)
            self.task_tree.column(c, stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=vsb.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        try:
            review_font = tkfont.nametofont("TkDefaultFont").copy()
        except Exception:
            review_font = tkfont.Font()
        review_font.configure(size=review_font.cget("size") + 3)
        style = ttk.Style(self.task_tree)
        style.configure("Review.Treeview", font=review_font)
        self.task_tree.configure(style="Review.Treeview")
        self.task_tree.tag_configure("open", foreground="red")
        resolved_font = review_font.copy()
        try:
            resolved_font.configure(overstrike=1)
        except Exception:
            pass
        self.task_tree.tag_configure("resolved", font=resolved_font, foreground="gray")
        self.task_tree.tag_configure("ignored", foreground="gray")
        # ReviewManager will attach event bindings

        btn_frame = tk.Frame(review_tab)
        btn_frame.pack(pady=(0, 5))
        tk.Button(btn_frame, text="Open", command=lambda: self.review.open_selected_items()).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Resolve", command=lambda: self.review.resolve_selected_tasks()).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Ignore", command=lambda: self.review.ignore_selected_tasks()).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Clear Resolved", command=lambda: self.review.remove_resolved_tasks()).pack(side="left", padx=2)

        self.review_menu = tk.Menu(self.task_tree, tearoff=0)
        self.review_menu.add_command(label="Open", command=lambda: self.review.open_selected_items())
        self.review_menu.add_command(label="Resolve", command=lambda: self.review.resolve_selected_tasks())
        self.review_menu.add_command(label="Ignore", command=lambda: self.review.ignore_selected_tasks())
        self.review_menu.add_command(label="Clear Resolved", command=lambda: self.review.remove_resolved_tasks())
        # Right-click handled by ReviewManager

        # Initialize review manager to handle flagged items
        self.review = ReviewManager(self, self.task_tree, self.review_menu)

        # Top-level menu bar
        menubar = tk.Menu(root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.on_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Settings", command=lambda: self.nb.select(self.settings_tab))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="About", menu=help_menu)
        root.config(menu=menubar)

        order_frame = tk.LabelFrame(order_tab, text="Order / File Input")
        order_frame.pack(fill="x", padx=5, pady=5)
        order_frame.grid_columnconfigure(1, weight=1)

        self.order_info_vars: dict[str, tk.StringVar] = {}

        info_frame = tk.Frame(order_frame)
        for row, (label, key) in enumerate(
            (("Order #", "order_id"), ("Company", "company"), ("Sales Rep", "sales_rep"))
        ):
            tk.Label(info_frame, text=label).grid(row=row, column=0, sticky="e")
            var = tk.StringVar()
            entry = tk.Entry(info_frame, textvariable=var, state="disabled", width=40)
            entry.grid(row=row, column=1, padx=5, pady=2, sticky="w")
            self.order_info_vars[key] = var
        info_frame.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 2))
        self.update_order_info()

        source_frame = tk.Frame(order_frame)
        source_frame.grid_columnconfigure(1, weight=1)
        source_frame.grid_columnconfigure(2, weight=1)
        source_frame.grid_columnconfigure(5, weight=1)
        tk.Label(source_frame, text="Order URL").grid(row=0, column=0, sticky="e")
        self.url_var = tk.StringVar()
        tk.Entry(source_frame, textvariable=self.url_var, width=50).grid(row=0, column=1, columnspan=4, padx=5, pady=2, sticky="w")
        self.url_var.trace_add("write", lambda *a: self.on_url_change())

        tk.Label(source_frame, text="Order IDs").grid(row=1, column=0, sticky="ne")
        self.order_id_var = tk.StringVar()
        self.ids_text = scrolledtext.ScrolledText(source_frame, width=20, height=4)
        self.ids_text.grid(row=1, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        self.fetch_id_job = None
        self.ids_text.bind("<KeyRelease>", lambda e: self.on_order_id_change())
        tk.Button(source_frame, text="Fetch", command=self.fetch_by_id).grid(row=1, column=3, padx=5, pady=2)
        tk.Button(source_frame, text="Load File", command=self.load_file).grid(row=1, column=4, padx=5, pady=2)
        tk.Button(source_frame, text="Get Vista Orders", command=self.fetch_vista_orders).grid(row=1, column=5, padx=5, pady=2)
        source_frame.grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.fields: dict[str, scrolledtext.ScrolledText] = {}

        table_section = tk.LabelFrame(order_tab, text="Order Items")
        table_section.pack(fill="x", padx=5, pady=(0, 5))
        table_frame = tk.Frame(table_section)
        style = ttk.Style(root)
        style.layout("NoHeading.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        self.item_table = ttk.Treeview(
            table_frame,
            columns=("order_id", "company"),
            show="headings",
            selectmode="browse",
            height=5,
            style="NoHeading.Treeview",
        )
        self.item_table.heading("order_id", text="Order #")
        self.item_table.heading("company", text="Company")
        for col, width in (("order_id", 120), ("company", 240)):
            self.item_table.column(col, width=width, anchor="w")
        self.item_table.bind("<<TreeviewSelect>>", self.on_table_select)
        self.item_table.pack(fill="x", padx=5, pady=(0, 5))
        table_frame.pack(anchor="w")

        prod_frame = tk.LabelFrame(order_frame, text="Production Info")
        prod_frame.grid_columnconfigure(0, weight=1)
        edit_frame = tk.Frame(prod_frame)
        for i in range(3):
            edit_frame.grid_columnconfigure(i, weight=1)
        for idx, (key, label, height) in enumerate(
            (
                ("gluetab", "Glue Tab", 3),
                ("info", "Info", 3),
                ("filename", "File Name", 1),
            )
        ):
            tk.Label(edit_frame, text=label).grid(row=0, column=idx, sticky="w")
            txt = scrolledtext.ScrolledText(
                edit_frame,
                width=25,
                height=height,
                font=("Courier New", 10),
            )
            txt.grid(row=1, column=idx, padx=2, pady=2)
            txt.config(state="disabled")
            self.fields[key] = txt
        edit_frame.grid(row=0, column=0, padx=5, pady=(0, 5), sticky="w")
        prod_frame.grid(row=2, column=0, sticky="w", padx=5, pady=(0, 5))

        # Per-pair template and art ID display
        pair_frame = tk.LabelFrame(order_tab, text="Current Pair")
        pair_frame.pack(fill="x", padx=5, pady=5)

        info_frame = tk.Frame(pair_frame)
        tk.Label(info_frame, text="Template").grid(row=0, column=0, sticky="w")
        self.cur_template_var = tk.StringVar()
        self.cur_template_entry = tk.Entry(info_frame, textvariable=self.cur_template_var, state="disabled", width=20)
        self.cur_template_entry.grid(row=0, column=1, padx=5, pady=2)
        tk.Label(info_frame, text="Art ID").grid(row=0, column=2, sticky="w")
        self.cur_artid_var = tk.StringVar()
        self.cur_artid_entry = tk.Entry(info_frame, textvariable=self.cur_artid_var, state="disabled", width=20)
        self.cur_artid_entry.grid(row=0, column=3, padx=5, pady=2)
        tk.Label(info_frame, text="Paper").grid(row=1, column=0, sticky="w")
        self.cur_paper_var = tk.StringVar()
        self.cur_paper_entry = tk.Entry(info_frame, textvariable=self.cur_paper_var, state="disabled", width=20)
        self.cur_paper_entry.grid(row=1, column=1, padx=5, pady=2)
        tk.Label(info_frame, text="Laminate").grid(row=1, column=2, sticky="w")
        self.cur_laminate_var = tk.StringVar()
        self.cur_laminate_entry = tk.Entry(info_frame, textvariable=self.cur_laminate_var, state="disabled", width=20)
        self.cur_laminate_entry.grid(row=1, column=3, padx=5, pady=2)
        tk.Label(info_frame, text="Setting").grid(row=2, column=0, sticky="w")
        self.cur_setting_var = tk.StringVar()
        self.cur_setting_entry = tk.Entry(info_frame, textvariable=self.cur_setting_var, state="disabled", width=20)
        self.cur_setting_entry.grid(row=2, column=1, padx=5, pady=2)
        self.coffee_label = tk.Label(info_frame, text="", fg="brown")
        self.coffee_label.grid(row=3, column=0, columnspan=4, sticky="w")
        info_frame.pack(padx=5, pady=2, anchor="w")

        self.item_label = tk.Label(pair_frame, text="Item 0/0")
        self.item_label.pack(pady=2)

        ctrl_frame = tk.Frame(pair_frame)
        self.edit_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl_frame, text="Edit", variable=self.edit_var, command=self.toggle_edit).pack(side="left")
        tk.Button(ctrl_frame, text="Prev", command=self.prev_item).pack(side="left")
        tk.Button(ctrl_frame, text="Next", command=self.next_item).pack(side="left")
        tk.Button(ctrl_frame, text="Add Order", command=self.add_order).pack(side="left")
        tk.Button(ctrl_frame, text="Clear", command=self.clear_batch).pack(side="left")
        tk.Button(ctrl_frame, text="Save JSON", command=self.save_json).pack(side="left")
        tk.Button(ctrl_frame, text="Save HTML", command=self.save_html).pack(side="left")
        tk.Button(ctrl_frame, text="Run Illustrator", command=self.run_illustrator).pack(side="left")
        tk.Button(ctrl_frame, text="Exit", command=self.on_exit).pack(side="left")
        ctrl_frame.pack(pady=5)
        tk.Label(pair_frame, textvariable=self.total_time_var).pack(pady=(0, 5))

        batch_frame = tk.LabelFrame(order_tab, text="Batch Orders")
        batch_frame.pack(fill="x", padx=5, pady=5)
        self.order_list = tk.Listbox(batch_frame, height=4, width=10, exportselection=False)
        self.order_list.pack(fill="x", padx=5, pady=(2, 0))
        self.order_list.config(state="disabled")

        # Checklist tab (pairs)
        self.pair_canvas = tk.Canvas(pairs_tab)
        self.pair_scroll = tk.Scrollbar(pairs_tab, orient="vertical", command=self.pair_canvas.yview)
        self.pair_frame = tk.Frame(self.pair_canvas)
        self.pair_frame.bind(
            "<Configure>", lambda e: self.pair_canvas.configure(scrollregion=self.pair_canvas.bbox("all"))
        )
        self.pair_canvas.create_window((0, 0), window=self.pair_frame, anchor="nw")
        self.pair_canvas.configure(yscrollcommand=self.pair_scroll.set)
        self.pair_canvas.pack(side="left", fill="both", expand=True)
        self.pair_scroll.pack(side="right", fill="y")
        self.count_label = tk.Label(pairs_tab, text="0 items")
        self.count_label.pack(side="bottom", anchor="e", padx=5, pady=2)
        self.pair_vars: list[tk.BooleanVar] = []
        self.foil_vars: list[tk.BooleanVar] = []
        self.emboss_vars: list[tk.BooleanVar] = []
        self.emboss_detected: bool = False

        # Settings tab controls
        self.login_url_var = tk.StringVar()
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.queue_login_url_var = tk.StringVar()
        self.queue_username_var = tk.StringVar()
        self.queue_password_var = tk.StringVar()
        self.queue_page_var = tk.StringVar()
        self.ill_path_var = tk.StringVar(value=ILLUSTRATOR_EXE)
        self.session = requests.Session()
        self.logged_in = False
        self.queue_session = requests.Session()
        self.logged_in_queue = False
        self.art_dir_var = tk.StringVar()
        self.template_dir_var = tk.StringVar()
        self.month_dir_var = tk.StringVar()
        self.summary_var = tk.BooleanVar()
        self.art_server_var = tk.StringVar()
        self.gdrive_var = tk.StringVar()
        self.chat_api_key_var = tk.StringVar()
        self.chat_api_url_var = tk.StringVar()
        self.chat_client = None
        self.appearance_var = tk.StringVar()
        self.diagnostic_var = tk.BooleanVar(value=False)
        self.review_flats_var = tk.BooleanVar(value=False)
        self.preserve_color_var = tk.BooleanVar(value=False)
        self.pending_flat_paths: list[str] = []
        self.pending_flat_info: list[
            tuple[str, str, int, str, str, str, str, str]
        ] = []
        # (flat path, order id, pair #, art id, gluetab, template, laminate, art path)

        settings = load_settings()
        self.diagnostic_var.set(settings.get("diagnostic_mode", False))
        self.review_flats_var.set(settings.get("review_flats", False))
        self.preserve_color_var.set(settings.get("preserve_color_profile", False))
        self.login_url_var.set(settings.get("login_url", ""))
        self.username_var.set(settings.get("username", ""))
        self.password_var.set(settings.get("password", ""))
        self.queue_login_url_var.set(settings.get("queue_login_url", ""))
        self.queue_username_var.set(settings.get("queue_username", ""))
        self.queue_password_var.set(settings.get("queue_password", ""))
        self.queue_page_var.set(settings.get("queue_page_url", ""))
        self.ill_path_var.set(settings.get("illustrator_path", ILLUSTRATOR_EXE))
        self.art_dir_var.set(settings.get("art_dir", ""))
        self.template_dir_var.set(settings.get("template_dir", ""))
        self.month_dir_var.set(settings.get("month_dir", ""))
        self.summary_var.set(settings.get("show_summary", False))
        self.art_server_var.set(settings.get("art_server_path", ""))
        self.gdrive_var.set(settings.get("gdrive_path", ""))
        self.chat_api_key_var.set(settings.get("chat_api_key", ""))
        self.chat_api_url_var.set(settings.get("chat_api_url", CHAT_API_URL))
        self.appearance_var.set(settings.get("appearance_mode", "System"))
        if ctk:
            ctk.set_appearance_mode(self.appearance_var.get())

        info_frame = tk.LabelFrame(settings_tab, text="Order Summary")
        info_frame.grid(row=0, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        paths_frame = tk.LabelFrame(settings_tab, text="Directories")
        paths_frame.grid(row=1, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        opts_frame = tk.LabelFrame(settings_tab, text="Options")
        opts_frame.grid(row=2, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        diag_frame = tk.LabelFrame(settings_tab, text="Diagnostics")
        diag_frame.grid(row=3, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        login_frame = tk.LabelFrame(settings_tab, text="Login Options")
        login_frame.grid(row=4, column=0, columnspan=3, sticky="we", padx=5, pady=5)
        appearance_frame = tk.LabelFrame(settings_tab, text="Appearance")
        appearance_frame.grid(row=5, column=0, columnspan=3, sticky="we", padx=5, pady=5)

        row = 0
        tk.Label(appearance_frame, text="Theme").grid(row=row, column=0, sticky="w")
        theme_menu = ttk.Combobox(
            appearance_frame,
            values=["System", "Light", "Dark"],
            textvariable=self.appearance_var,
            state="readonly",
            width=10,
        )
        theme_menu.grid(row=row, column=1, padx=5, pady=2)
        if ctk:
            theme_menu.bind(
                "<<ComboboxSelected>>",
                lambda e: ctk.set_appearance_mode(self.appearance_var.get()),
            )

        row = 0
        tk.Label(info_frame, text="Templates").grid(row=row, column=0, sticky="w")
        self.templates_entry = tk.Entry(info_frame, state="disabled", width=50)
        self.templates_entry.grid(row=row, column=1, columnspan=2, padx=5, pady=2, sticky="we")
        row += 1
        tk.Label(info_frame, text="Art IDs").grid(row=row, column=0, sticky="w")
        self.artids_entry = tk.Entry(info_frame, state="disabled", width=50)
        self.artids_entry.grid(row=row, column=1, columnspan=2, padx=5, pady=2, sticky="we")

        row = 0
        tk.Label(paths_frame, text="Art Folder").grid(row=row, column=0, sticky="w")
        tk.Entry(paths_frame, textvariable=self.art_dir_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        tk.Button(paths_frame, text="Browse", command=self.browse_art_dir).grid(row=row, column=2, padx=5, pady=2)
        row += 1

        tk.Label(paths_frame, text="Template Folder").grid(row=row, column=0, sticky="w")
        tk.Entry(paths_frame, textvariable=self.template_dir_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        tk.Button(paths_frame, text="Browse", command=self.browse_template_dir).grid(row=row, column=2, padx=5, pady=2)
        row += 1

        tk.Label(paths_frame, text="Month Folder").grid(row=row, column=0, sticky="w")
        tk.Entry(paths_frame, textvariable=self.month_dir_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        tk.Button(paths_frame, text="Browse", command=self.browse_month_dir).grid(row=row, column=2, padx=5, pady=2)
        row += 1

        tk.Label(paths_frame, text="Art Server Path").grid(row=row, column=0, sticky="w")
        tk.Entry(paths_frame, textvariable=self.art_server_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        tk.Button(paths_frame, text="Browse", command=self.browse_art_server).grid(row=row, column=2, padx=5, pady=2)
        row += 1

        tk.Label(paths_frame, text="Google Drive Path").grid(row=row, column=0, sticky="w")
        tk.Entry(paths_frame, textvariable=self.gdrive_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        tk.Button(paths_frame, text="Browse", command=self.browse_gdrive).grid(row=row, column=2, padx=5, pady=2)

        row = 0
        tk.Label(opts_frame, text="Illustrator Path").grid(row=row, column=0, sticky="w")
        tk.Entry(opts_frame, textvariable=self.ill_path_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        tk.Button(opts_frame, text="Browse", command=self.browse_illustrator).grid(row=row, column=2, padx=5, pady=2)
        row += 1
        tk.Checkbutton(opts_frame, text="Show Summary", variable=self.summary_var).grid(row=row, column=0, sticky="w")
        row += 1
        tk.Checkbutton(opts_frame, text="Preserve Color Profile", variable=self.preserve_color_var).grid(row=row, column=0, sticky="w")

        row = 0
        tk.Checkbutton(
            diag_frame,
            text="Diagnostic mode (save to '--DO NOT USE - PRINT--')",
            variable=self.diagnostic_var,
        ).grid(row=row, column=0, sticky="w")
        row += 1
        tk.Button(
            diag_frame,
            text="Open Art Directories",
            command=self.open_art_dirs,
        ).grid(row=row, column=0, pady=2, sticky="w")
        row += 1
        tk.Button(
            diag_frame,
            text="Move art to art folders",
            command=self.move_art_to_art_folders,
        ).grid(row=row, column=0, pady=2, sticky="w")
        row += 1
        tk.Checkbutton(
            diag_frame,
            text="Review flat PDFs after processing",
            variable=self.review_flats_var,
        ).grid(row=row, column=0, sticky="w")
        row += 1
        tk.Button(
            diag_frame,
            text="History",
            command=self.show_dashboard,
        ).grid(row=row, column=0, pady=2, sticky="w")
        row += 1
        tk.Button(
            diag_frame,
            text="Template Settings",
            command=self.open_template_settings_editor,
        ).grid(row=row, column=0, pady=2, sticky="w")

        row = 0
        tk.Button(login_frame, text="Login Art Server", command=self.check_art_server).grid(row=row, column=0, pady=2, sticky="w")
        self.art_server_status = tk.Label(login_frame, text="Disconnected", fg="red")
        self.art_server_status.grid(row=row, column=1, sticky="w")
        row += 1
        tk.Button(login_frame, text="Disconnect", command=self.disconnect_art_server).grid(row=row, column=0, pady=2, sticky="w")
        row += 1

        tk.Button(login_frame, text="Login Google Drive", command=self.check_gdrive).grid(row=row, column=0, pady=2, sticky="w")
        self.gdrive_status = tk.Label(login_frame, text="Disconnected", fg="red")
        self.gdrive_status.grid(row=row, column=1, sticky="w")
        row += 1
        tk.Button(login_frame, text="Disconnect", command=self.disconnect_gdrive).grid(row=row, column=0, pady=2, sticky="w")
        row += 1

        tk.Label(login_frame, text="Login URL").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.login_url_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Label(login_frame, text="Username").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.username_var, width=30).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Label(login_frame, text="Password").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.password_var, width=30, show="*").grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Button(login_frame, text="Login", command=self.login).grid(row=row, column=0, pady=5, sticky="w")
        self.login_status = tk.Label(login_frame, text="Not logged in", fg="red")
        self.login_status.grid(row=row, column=1, sticky="w")
        row += 1
        tk.Button(login_frame, text="Disconnect", command=self.logout).grid(row=row, column=0, pady=2, sticky="w")
        row += 1

        tk.Label(login_frame, text="Queue Login URL").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.queue_login_url_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Label(login_frame, text="Queue Username").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.queue_username_var, width=30).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Label(login_frame, text="Queue Password").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.queue_password_var, width=30, show="*").grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Label(login_frame, text="Queue Page URL").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.queue_page_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Button(login_frame, text="Login Queue", command=self.login_queue).grid(row=row, column=0, pady=5, sticky="w")
        self.queue_login_status = tk.Label(login_frame, text="Not logged in", fg="red")
        self.queue_login_status.grid(row=row, column=1, sticky="w")
        row += 1
        tk.Button(login_frame, text="Disconnect", command=self.logout_queue).grid(row=row, column=0, pady=2, sticky="w")
        row += 1
        self.login_log = scrolledtext.ScrolledText(login_frame, width=60, height=6, state="disabled", font=("Courier New", 9))
        self.login_log.grid(row=row, column=0, columnspan=3, padx=5, pady=2)
        row += 1
        tk.Label(login_frame, text="ChatGPT API Key").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.chat_api_key_var, width=50, show="*").grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Label(login_frame, text="ChatGPT API URL").grid(row=row, column=0, sticky="w")
        tk.Entry(login_frame, textvariable=self.chat_api_url_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        tk.Button(login_frame, text="Login ChatGPT", command=self.check_chat_api).grid(row=row, column=0, pady=2, sticky="w")
        self.chat_status = tk.Label(login_frame, text="Disconnected", fg="red")
        self.chat_status.grid(row=row, column=1, sticky="w")
        row += 1
        tk.Button(login_frame, text="Disconnect", command=self.disconnect_chat_api).grid(row=row, column=0, pady=2, sticky="w")


        # Initialize status indicators
        self.check_art_server()
        self.check_gdrive()
        self.update_chat_status()

    def toggle_edit(self):
        self.editable = self.edit_var.get()
        for txt in self.fields.values():
            txt.config(state="normal" if self.editable else "disabled")

    def update_order_info(self, info: dict | None = None):
        info = info or {}
        self.order_info_vars["order_id"].set(info.get("order_id", ""))
        self.order_info_vars["company"].set(info.get("company", ""))
        self.order_info_vars["sales_rep"].set(info.get("created_by", ""))

    def update_checklist_count(self, count: int):
        """Display how many items appear in the checklist."""
        text = f"{count} item" if count == 1 else f"{count} items"
        self.count_label.config(text=text)

    def log_message(self, text: str):
        """Append a line of text to the login log."""
        self.login_log.config(state="normal")
        self.login_log.insert(tk.END, text + "\n")
        self.login_log.see(tk.END)
        self.login_log.config(state="disabled")

    def append_chat(self, sender: str, text: str):
        """Add a message to the chat log instantly."""
        self.chat_log.config(state="normal")
        self.chat_log.insert(tk.END, f"{sender}: {text}\n\n")
        self.chat_log.see(tk.END)
        self.chat_log.config(state="disabled")

    def stream_chat(self, sender: str, text: str, delay: int = 10):
        """Type out the given text like a fast AI response."""

        def step(idx: int = 0):
            if idx == 0:
                self.chat_log.config(state="normal")
                self.chat_log.insert(tk.END, f"{sender}: ")
            if idx < len(text):
                self.chat_log.config(state="normal")
                self.chat_log.insert(tk.END, text[idx])
                self.chat_log.see(tk.END)
                self.chat_log.config(state="disabled")
                self.root.after(delay, step, idx + 1)
            else:
                self.chat_log.config(state="normal")
                self.chat_log.insert(tk.END, "\n\n")
                self.chat_log.see(tk.END)
                self.chat_log.config(state="disabled")

        step()

    def send_chat(self):
        """Send the user's chat message to the API and display a streaming reply."""
        msg = self.chat_input_var.get().strip()
        if not msg:
            return
        if msg.lower() in {"/summary", "summary"}:
            self.chat_input_var.set("")
            summary = summarize_history()
            self.stream_chat("Bot", summary)
            return
        self.chat_input_var.set("")
        self.append_chat("You", msg)

        def worker(prompt: str):
            client = self.chat_client
            if client is None:
                api_key = self.chat_api_key_var.get().strip()
                if not api_key:
                    self.root.after(0, lambda: self.append_chat("System", "Set your API key in Settings"))
                    return
                api_url = self.chat_api_url_var.get().strip() or CHAT_API_URL
                if not api_url.rstrip("/").endswith("/v1"):
                    api_url = api_url.rstrip("/") + "/v1"
                client = openai.OpenAI(api_key=api_key, base_url=api_url)
                self.chat_client = client
            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                )
                reply = resp.choices[0].message.content.strip()
            except Exception as exc:
                reply = f"Error: {exc}"
                self.chat_client = None
            self.root.after(0, self.update_chat_status)
            self.root.after(0, lambda: self.stream_chat("Bot", reply))

        threading.Thread(target=worker, args=(msg,), daemon=True).start()

    def update_timer(self):
        if self.run_start_time is None:
            return
        elapsed = time.time() - self.run_start_time
        self.total_time_var.set(f"Total time: {int(elapsed)}s")
        self.root.after(1000, self.update_timer)

    def on_exit(self):
        self.save_settings()
        # Persist unresolved flagged items
        if hasattr(self, "review"):
            save_flags(self.review.flagged_items)
        self.root.quit()

    def show_about(self):
        """Display program information."""
        messagebox.showinfo(
            "About",
            "Illustrator Automation GUI\nProvides batch template processing via Illustrator.",
        )

    def show_dashboard(self):
        """Display a simple history dashboard window."""
        hist = load_run_history()
        win = tk.Toplevel(self.root)
        win.title("Run History")
        text = scrolledtext.ScrolledText(win, width=80, height=20)
        text.pack(fill="both", expand=True)
        text.insert(tk.END, summarize_history() + "\n\n")
        for run in hist:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(run.get("timestamp", 0)))
            dur = run.get("duration", 0)
            flagged = run.get("flagged", [])
            line = f"{ts} - {dur:.1f}s - {len(flagged)} flagged"
            text.insert(tk.END, line + "\n")
            for item in flagged:
                name = os.path.basename(item.get("path", ""))
                reason = ", ".join(item.get("reasons", item.get("reason", "")))
                text.insert(tk.END, f"    {name}: {reason}\n")
        text.config(state="disabled")

    def open_template_settings_editor(self, code: str | None = None):
        """Open a dialog for editing template settings JSON files.

        If ``code`` is provided, ensure an entry exists and select it for editing.
        """
        win = tk.Toplevel(self.root)
        win.title("Template Settings")

        search_var = tk.StringVar()
        search_frame = tk.Frame(win)
        search_frame.pack(fill="x", padx=5, pady=(5, 0))
        tk.Label(search_frame, text="Search").pack(side="left")
        tk.Entry(search_frame, textvariable=search_var).pack(
            side="left", fill="x", expand=True, padx=5
        )
        tk.Button(search_frame, text="Clear", command=lambda: search_var.set("")).pack(
            side="left"
        )

        table_frame = tk.Frame(win)
        table_frame.pack(fill="both", expand=True, padx=5, pady=5)
        columns = ("code", "rotation", "bleed", "mirror", "artworkScale")
        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        tree.pack(side="left", fill="both", expand=True)
        for col in columns:
            tree.heading(col, text=col.title())
            width = 120 if col != "bleed" else 240
            tree.column(col, width=width, anchor="w")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")

        rotation_var = tk.StringVar()
        bleed_var = tk.StringVar()
        mirror_var = tk.BooleanVar()
        scale_var = tk.StringVar()
        status_var = tk.StringVar()
        unsaved = {"flag": False}

        def refresh_table(*_):
            sel = tree.selection()
            tree.delete(*tree.get_children())
            term = search_var.get().strip().upper()
            for f in sorted(TEMPLATE_SETTINGS_DIR.glob("*.json")):
                if f.name == "schema.json":
                    continue
                code = f.stem
                if term and term not in code.upper():
                    continue
                data = load_template_settings(code)
                rot = data.get("rotation", "")
                bleed = ", ".join(data.get("bleedPaths", []))
                mirror = data.get("mirror", False)
                scale = data.get("artworkScale", "")
                tree.insert(
                    "",
                    "end",
                    iid=code,
                    values=(code, rot, bleed, mirror, scale),
                )
            if sel and sel[0] in tree.get_children():
                tree.selection_set(sel[0])
                load_selected()

        search_var.trace_add("write", refresh_table)

        def load_selected(event=None):
            sel = tree.selection()
            if not sel:
                return
            code = sel[0]
            data = load_template_settings(code)
            rotation_var.set(str(data.get("rotation", "")))
            bleed_var.set(", ".join(data.get("bleedPaths", [])))
            mirror_var.set(bool(data.get("mirror", False)))
            scale_var.set(str(data.get("artworkScale", "")))
            unsaved["flag"] = False
            update_state()
            tags = tuple(t for t in tree.item(code, "tags") if t != "unsaved")
            tree.item(code, tags=tags)

        tree.bind("<<TreeviewSelect>>", load_selected)

        edit_frame = tk.Frame(win)
        edit_frame.pack(fill="x", padx=5, pady=5)
        tk.Label(edit_frame, text="Rotation").grid(row=0, column=0, sticky="w")
        tk.Entry(edit_frame, textvariable=rotation_var).grid(row=0, column=1, sticky="we")
        tk.Label(edit_frame, text="Bleed Paths").grid(row=1, column=0, sticky="w")
        tk.Entry(edit_frame, textvariable=bleed_var).grid(row=1, column=1, sticky="we")
        tk.Checkbutton(edit_frame, text="Mirror", variable=mirror_var).grid(
            row=2, column=0, columnspan=2, sticky="w"
        )
        tk.Label(edit_frame, text="Artwork Scale").grid(row=3, column=0, sticky="w")
        tk.Entry(edit_frame, textvariable=scale_var).grid(row=3, column=1, sticky="we")
        edit_frame.grid_columnconfigure(1, weight=1)

        def validate() -> bool:
            rot = rotation_var.get().strip()
            bleed = bleed_var.get().strip()
            scale = scale_var.get().strip()
            if not rot or not bleed or not scale:
                return False
            try:
                int(rot)
            except ValueError:
                return False
            try:
                if float(scale) < 0:
                    return False
            except ValueError:
                return False
            return True

        def mark_unsaved(*_):
            sel = tree.selection()
            if not sel:
                return
            unsaved["flag"] = True
            item_id = sel[0]
            tags = tree.item(item_id, "tags")
            if "unsaved" not in tags:
                tree.item(item_id, tags=tags + ("unsaved",))
            update_state()

        rotation_var.trace_add("write", mark_unsaved)
        bleed_var.trace_add("write", mark_unsaved)
        mirror_var.trace_add("write", mark_unsaved)
        scale_var.trace_add("write", mark_unsaved)

        def update_state():
            if unsaved["flag"] and validate():
                save_btn.config(state="normal")
            else:
                save_btn.config(state="disabled")

        def save():
            sel = tree.selection()
            if not sel:
                return
            code = sel[0]
            updates: dict[str, object] = {}
            rot_text = rotation_var.get().strip()
            updates["rotation"] = int(rot_text)
            paths = [p.strip() for p in re.split(r"[,\s]+", bleed_var.get()) if p.strip()]
            updates["bleedPaths"] = paths
            updates["mirror"] = mirror_var.get()
            scale_text = scale_var.get().strip()
            updates["artworkScale"] = float(scale_text)
            try:
                update_template_settings(code, updates)
                tree.item(
                    code,
                    values=(
                        code,
                        updates["rotation"],
                        ", ".join(paths),
                        updates["mirror"],
                        updates["artworkScale"],
                    ),
                )
                status_var.set("Saved")
                win.after(2000, lambda: status_var.set(""))
                unsaved["flag"] = False
                update_state()
                tags = tuple(t for t in tree.item(code, "tags") if t != "unsaved")
                tree.item(code, tags=tags)
            except Exception as exc:
                messagebox.showerror("Error", str(exc))

        def add_new():
            class NewTemplateDialog(simpledialog.Dialog):
                def body(self, master):
                    tk.Label(master, text="Template code:").grid(row=0, column=0, sticky="e")
                    self.code_var = tk.StringVar()
                    code_entry = tk.Entry(master, textvariable=self.code_var)
                    code_entry.grid(row=0, column=1, sticky="we")

                    tk.Label(master, text="Rotation:").grid(row=1, column=0, sticky="e")
                    self.rotation_var = tk.StringVar(value="0")
                    tk.Entry(master, textvariable=self.rotation_var).grid(row=1, column=1, sticky="we")

                    tk.Label(master, text="Bleed paths:").grid(row=2, column=0, sticky="e")
                    self.bleed_var = tk.StringVar()
                    tk.Entry(master, textvariable=self.bleed_var).grid(row=2, column=1, sticky="we")

                    self.mirror_var = tk.BooleanVar(value=False)
                    tk.Checkbutton(master, text="Mirror", variable=self.mirror_var).grid(row=3, column=1, sticky="w")

                    tk.Label(master, text="Artwork scale:").grid(row=4, column=0, sticky="e")
                    self.scale_var = tk.StringVar(value="1")
                    tk.Entry(master, textvariable=self.scale_var).grid(row=4, column=1, sticky="we")

                    return code_entry

                def validate(self):
                    code = self.code_var.get().strip().upper()
                    if not code:
                        messagebox.showerror("Error", "Template code is required", parent=self)
                        return False
                    try:
                        rotation = int(self.rotation_var.get().strip() or "0")
                    except ValueError:
                        messagebox.showerror("Error", "Rotation must be an integer", parent=self)
                        return False
                    try:
                        scale = float(self.scale_var.get().strip() or "1")
                        if scale < 0:
                            raise ValueError
                    except ValueError:
                        messagebox.showerror("Error", "Scale must be a non-negative number", parent=self)
                        return False
                    bleed = [p.strip() for p in re.split(r"[,\s]+", self.bleed_var.get()) if p.strip()]
                    self.result = {
                        "code": code,
                        "rotation": rotation,
                        "bleedPaths": bleed,
                        "mirror": self.mirror_var.get(),
                        "artworkScale": scale,
                    }
                    return True

                def apply(self):
                    pass

            dialog = NewTemplateDialog(win)
            if not getattr(dialog, "result", None):
                return
            code = dialog.result["code"]
            data = {
                "rotation": dialog.result["rotation"],
                "bleedPaths": dialog.result["bleedPaths"],
                "mirror": dialog.result["mirror"],
                "artworkScale": dialog.result["artworkScale"],
            }
            try:
                save_template_settings(code, data)
            except Exception as exc:
                messagebox.showerror("Error", str(exc))
                return
            refresh_table()
            tree.selection_set(code)
            load_selected()

        def delete_selected():
            sel = tree.selection()
            if not sel:
                return
            code = sel[0]
            path = TEMPLATE_SETTINGS_DIR / f"{code}.json"
            if messagebox.askyesno("Delete", f"Delete settings for {code}?"):
                try:
                    path.unlink(missing_ok=True)
                    refresh_table()
                    rotation_var.set("")
                    bleed_var.set("")
                    mirror_var.set(False)
                    scale_var.set("")
                    unsaved["flag"] = False
                    update_state()
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

        def export_settings():
            path = filedialog.asksaveasfilename(
                title="Export Template Settings",
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
            )
            if not path:
                return
            try:
                export_template_settings(path)
                messagebox.showinfo("Exported", f"Settings exported to {path}")
            except Exception as exc:
                messagebox.showerror("Error", str(exc))

        def import_settings():
            path = filedialog.askopenfilename(
                title="Import Template Settings",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
            )
            if not path:
                return
            try:
                import_template_settings(path, overwrite=False)
            except FileExistsError:
                if not messagebox.askyesno(
                    "Overwrite?",
                    "Importing will overwrite existing settings. Continue?",
                ):
                    return
                try:
                    import_template_settings(path, overwrite=True)
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))
                    return
            except Exception as exc:
                messagebox.showerror("Error", str(exc))
                return
            refresh_table()

        btn_frame = tk.Frame(edit_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=5)
        save_btn = tk.Button(btn_frame, text="Save", state="disabled", command=save)
        save_btn.pack(side="left", padx=2)
        tk.Button(btn_frame, text="Add", command=add_new).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Delete", command=delete_selected).pack(side="left", padx=2)
        tk.Label(edit_frame, textvariable=status_var, fg="green").grid(
            row=5, column=0, columnspan=2, sticky="w"
        )
        io_frame = tk.Frame(edit_frame)
        io_frame.grid(row=6, column=0, columnspan=2, pady=5)
        tk.Button(io_frame, text="Export", command=export_settings).pack(side="left", padx=2)
        tk.Button(io_frame, text="Import", command=import_settings).pack(side="left", padx=2)

        tree.tag_configure("unsaved", background="#fff3cd")
        refresh_table()
        if code:
            code = code.strip().upper()
            path = TEMPLATE_SETTINGS_DIR / f"{code}.json"
            if not path.exists():
                try:
                    save_template_settings(code, {})
                    refresh_table()
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))
            if path.exists():
                tree.selection_set(code)
                load_selected()

    def save_settings(self):
        data = {
            "login_url": self.login_url_var.get(),
            "username": self.username_var.get(),
            "password": self.password_var.get(),
            "queue_login_url": self.queue_login_url_var.get(),
            "queue_username": self.queue_username_var.get(),
            "queue_password": self.queue_password_var.get(),
            "queue_page_url": self.queue_page_var.get(),
            "illustrator_path": self.ill_path_var.get(),
            "art_dir": self.art_dir_var.get(),
            "template_dir": self.template_dir_var.get(),
            "month_dir": self.month_dir_var.get(),
            "order_id": self.order_id_var.get(),
            "show_summary": self.summary_var.get(),
            "art_server_path": self.art_server_var.get(),
            "gdrive_path": self.gdrive_var.get(),
            "chat_api_key": self.chat_api_key_var.get(),
            "chat_api_url": self.chat_api_url_var.get(),
            "appearance_mode": self.appearance_var.get(),
            "diagnostic_mode": self.diagnostic_var.get(),
            "review_flats": self.review_flats_var.get(),
            "preserve_color_profile": self.preserve_color_var.get(),
        }
        save_settings(data)

    def update_pair_display(self):
        temps = " | ".join(p.get("template", "") for p in self.pairs)
        art_ids = " | ".join(p.get("art_id", "") for p in self.pairs)
        for entry, text in (
            (self.templates_entry, temps),
            (self.artids_entry, art_ids),
        ):
            entry.config(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, text)
            entry.config(state="disabled")

    def update_item_table(self):
        self.item_table.delete(*self.item_table.get_children())
        items_src = self.batch_items if self.batch_items else self.items
        pair_counters: dict[str, int] = {}
        for idx, item in enumerate(items_src):
            oid = item.get("order_id") or self.order_id_var.get()
            pair_counters[oid] = pair_counters.get(oid, 0) + 1
            display_oid = f"{oid}.{pair_counters[oid]}" if oid else f".{pair_counters[oid]}"
            self.item_table.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    display_oid,
                    item.get("company", ""),
                ),
            )
        if items_src:
            try:
                self._ignore_table_event = True
                self.item_table.selection_set(str(self.index))
                self.item_table.see(str(self.index))
            finally:
                self._ignore_table_event = False

    def show_missing_templates_window(self, missing: list[str]):
        """Display or update a popup listing missing templates."""
        if self.missing_templates_win and self.missing_templates_win.winfo_exists():
            win = self.missing_templates_win
            log = self.missing_templates_log
            log.config(state="normal")
            log.delete("1.0", tk.END)
        else:
            win = tk.Toplevel(self.root)
            win.title("Missing Templates")
            win.attributes("-topmost", True)
            font_size = int(tkfont.nametofont("TkFixedFont").cget("size") * 1.2)
            log = scrolledtext.ScrolledText(
                win,
                width=60,
                height=10,
                state="normal",
                background="black",
                foreground="red",
                font=("Courier New", font_size),
            )
            log.pack(fill="both", expand=True, padx=20, pady=20)
            tk.Button(win, text="Close", command=win.withdraw).pack(pady=(0, 10))
            win.protocol("WM_DELETE_WINDOW", win.withdraw)
            self.missing_templates_win = win
            self.missing_templates_log = log

        log.insert(tk.END, "Missing templates:\n\n")
        for tmpl in sorted(missing):
            log.insert(tk.END, tmpl + "\n")
        log.config(state="disabled")
        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_width()) // 2
        y = (win.winfo_screenheight() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.deiconify()

    def show_missing_cut_window(self, missing: list[str]):
        """Display or update a popup listing missing cut files."""
        if self.missing_cut_win and self.missing_cut_win.winfo_exists():
            win = self.missing_cut_win
            log = self.missing_cut_log
            log.config(state="normal")
            log.delete("1.0", tk.END)
        else:
            win = tk.Toplevel(self.root)
            win.title("Missing Cut Files")
            win.attributes("-topmost", True)
            font_size = int(tkfont.nametofont("TkFixedFont").cget("size") * 1.2)
            log = scrolledtext.ScrolledText(
                win,
                width=60,
                height=10,
                state="normal",
                background="black",
                foreground="red",
                font=("Courier New", font_size),
            )
            log.pack(fill="both", expand=True, padx=20, pady=20)
            tk.Button(win, text="Close", command=win.withdraw).pack(pady=(0, 10))
            win.protocol("WM_DELETE_WINDOW", win.withdraw)
            self.missing_cut_win = win
            self.missing_cut_log = log

        log.insert(tk.END, "Missing cut files:\n\n")
        for path in sorted(missing):
            log.insert(tk.END, path + "\n")
        log.config(state="disabled")
        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_width()) // 2
        y = (win.winfo_screenheight() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.deiconify()

    def copy_cut_files(self):
        """Copy cut files for sample orders and show a warning if any are missing."""
        if not self.sample_copy_info:
            return
        missing: list[str] = []
        for src, dest_dir in self.sample_copy_info:
            if not src or not os.path.isfile(src):
                missing.append(src or "<unknown>")
                continue
            try:
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy(src, dest_dir)
            except Exception:
                missing.append(src)
        self.sample_copy_info.clear()
        if missing:
            self.show_missing_cut_window(missing)

    def check_missing_templates(self):
        """Check all loaded pairs for missing templates and display them."""
        temp_dir = self.template_dir_var.get()
        if not temp_dir:
            return
        pairs = self.batch_pairs if self.batch_pairs else self.pairs
        items = self.batch_items if self.batch_items else self.items
        missing: list[str] = []
        for idx, p in enumerate(pairs):
            code = p.get("template", "").strip()
            if not code:
                continue
            qty = get_item_quantity(items[idx]) if idx < len(items) else 0
            sample = qty == 11
            if not find_template_file(temp_dir, code, sample=sample):
                label = f"{code} (sample)" if sample else code
                if label not in missing:
                    missing.append(label)
        if missing:
            self.show_missing_templates_window(missing)
        elif self.missing_templates_win and self.missing_templates_win.winfo_exists():
            self.missing_templates_win.withdraw()

    def on_table_select(self, event):
        if self._ignore_table_event:
            return
        sel = self.item_table.selection()
        if sel:
            try:
                idx = int(sel[0])
                if self.index != idx:
                    self.index = idx
                    self.update_fields()
            except Exception:
                pass

    def on_order_id_change(self):
        """Delay fetch until typing stops."""
        if self.fetch_id_job is not None:
            self.root.after_cancel(self.fetch_id_job)
        text = self.ids_text.get("1.0", tk.END).strip()
        if text:
            self.fetch_id_job = self.root.after(500, self.fetch_by_id)

    def on_url_change(self):
        """Extract the order number from the URL and update the field."""
        if self._ignore_url_change:
            return
        url = self.url_var.get()
        m = re.search(r"id=(\d+)", url)
        if m:
            order_id = m.group(1)
            self.order_id_var.set(order_id)
            ids = self.ids_text.get("1.0", tk.END).strip().split()
            if order_id not in ids:
                if ids:
                    self.ids_text.insert(tk.END, "\n" + order_id)
                else:
                    self.ids_text.insert(tk.END, order_id)
            self.on_order_id_change()

    def fetch_by_id(self):
        """Build the order URL from the entered ID and fetch the data."""
        if self.fetch_id_job is not None:
            self.root.after_cancel(self.fetch_id_job)
            self.fetch_id_job = None
        raw = self.ids_text.get("1.0", tk.END)
        order_ids = re.findall(r"\d+", raw)
        if not order_ids:
            return
        # Skip IDs that have already been processed
        new_ids = [oid for oid in order_ids if oid not in self.batch_orders]
        if not new_ids:
            return
        self._ignore_url_change = True
        for oid in new_ids:
            self.order_id_var.set(oid)
            self.url_var.set(ORDER_BASE_URL + oid)
            self.fetch()
        self._ignore_url_change = False

    def update_fields(self):
        current_items = self.items if self.items else self.batch_items
        current_pairs = self.pairs if self.items else self.batch_pairs
        if not current_items:
            for txt in self.fields.values():
                txt.config(state="normal")
                txt.delete("1.0", tk.END)
                txt.config(state="disabled")
            self.item_label.config(text="Item 0/0")
            for entry in (
                self.cur_template_entry,
                self.cur_artid_entry,
                self.cur_paper_entry,
                self.cur_laminate_entry,
                self.cur_setting_entry,
            ):
                entry.config(state="normal")
                entry.delete(0, tk.END)
                if entry is self.cur_laminate_entry:
                    color = get_laminate_color("")
                    entry.config(foreground=color, disabledforeground=color)
                if entry is self.cur_setting_entry:
                    entry.config(foreground="black", disabledforeground="black")
                entry.config(state="disabled")
            self.coffee_label.config(text="")
            self.update_pair_display()
            self.update_order_info()
            return

        item = current_items[self.index]
        self.item_label.config(text=f"Item {self.index + 1}/{len(current_items)}")
        for key, txt in self.fields.items():
            txt.config(state="normal")
            txt.delete("1.0", tk.END)
            txt.insert("1.0", item.get(key, ""))
            if not self.editable:
                txt.config(state="disabled")
        template = ""
        art_id = ""
        if current_pairs and self.index < len(current_pairs):
            pair = current_pairs[self.index]
            template = pair.get("template", "")
            art_id = pair.get("art_id", "")
        paper = item.get("paperType", "")
        lam = item.get("lamType", "") or detect_laminate(item.get("info", ""))
        if not lam and is_coffee_sleeve(template):
            lam = "Uncoated"
        if template and not paper:
            path = find_template_file(self.template_dir_var.get(), template)
            paper = extract_paper_type(path)
        item["paperType"] = paper
        settings = load_template_settings(template)
        setting_val = template
        for entry, val in (
            (self.cur_template_entry, template),
            (self.cur_artid_entry, art_id),
            (self.cur_paper_entry, paper),
            (self.cur_laminate_entry, lam),
            (self.cur_setting_entry, setting_val),
        ):
            entry.config(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, val)
            if entry is self.cur_laminate_entry:
                color = get_laminate_color(val)
                entry.config(
                    foreground=color,
                    disabledforeground=color,
                )
            if entry is self.cur_setting_entry:
                has_settings = bool(settings)
                color = "#FF00FF" if has_settings else "black"
                entry.config(foreground=color, disabledforeground=color)
            entry.config(state="disabled")

        specials = []
        if is_coffee_sleeve(template):
            specials.append("Coffee Sleeve")
        if settings.get("bleedPaths") and len(settings["bleedPaths"]) > 1 and not is_coffee_sleeve(template):
            specials.append(f"{len(settings['bleedPaths'])}up")
        elif is_pb001(template):
            specials.append("2up")
        rot = settings.get("rotation")
        if rot == 180 or is_pb005(template):
            specials.append("180°")
        elif rot == 90 and not is_coffee_sleeve(template):
            specials.append("90°")
        self.coffee_label.config(text=", ".join(specials))

        # Highlight art ID matches in the filename field
        fname_txt = self.fields.get("filename")
        if fname_txt is not None:
            fname_txt.config(state="normal")
            fname_txt.tag_delete("match")
            fname_txt.tag_delete("mismatch")
            fname_txt.tag_remove("match", "1.0", tk.END)
            fname_txt.tag_remove("mismatch", "1.0", tk.END)
            found = False
            if art_id:
                pos = fname_txt.search(art_id, "1.0", tk.END, nocase=True)
                if pos:
                    end = f"{pos}+{len(art_id)}c"
                    fname_txt.tag_add("match", pos, end)
                    found = True
                else:
                    fname_txt.tag_add("mismatch", "1.0", tk.END)
            fname_txt.tag_config("match", foreground="green")
            fname_txt.tag_config("mismatch", foreground="red")
            if not self.editable:
                fname_txt.config(state="disabled")

        color = "green" if art_id and fname_txt and fname_txt.search(art_id, "1.0", tk.END, nocase=True) else "red"
        self.cur_artid_entry.config(state="normal")
        self.cur_artid_entry.config(foreground=color, disabledforeground=color)
        self.cur_artid_entry.config(state="disabled")

        self.update_pair_display()
        self.update_item_table()
        info_data = {
            k: item.get(k, "")
            for k in ("order_id", "company", "created_by")
            if item.get(k)
        }
        if info_data:
            self.update_order_info(info_data)

    def fetch(self):
        try:
            url = self.url_var.get()
            if url:
                if (
                    self.username_var.get()
                    and self.password_var.get()
                    and self.login_url_var.get()
                ):
                    if not self.logged_in:
                        self.login()
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = self.session.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                html = resp.text
                self.html_content = html
                self.emboss_detected = detect_emboss(html)
                save_order_html(html)
                self.temp_path = save_temp_html(html)
                try:
                    data = parse_order_json(html)
                except Exception:
                    data = parse_order(html)
                self.items = data.get("items", [])
                self.pairs = data.get("pairs", [])
                self.update_order_info(data.get("order_info"))
                if data.get("art_dir"):
                    self.art_dir_var.set(data["art_dir"])
                if data.get("template_dir"):
                    self.template_dir_var.set(data["template_dir"])
                if data.get("month_dir"):
                    self.month_dir_var.set(data["month_dir"])
                if data.get("order_id"):
                    self.order_id_var.set(str(data["order_id"]))
                if not self.pairs:
                    messagebox.showerror(
                        "Parse error", "Could not extract template / art IDs."
                    )
            if not self.items:
                messagebox.showerror("Error", "No order data found")
                return
            self.index = 0
            count = populate_pairs(
                self.pair_frame,
                self.pair_vars,
                self.items,
                self.pairs,
                self.foil_vars,
                self.emboss_vars,
                self.emboss_detected,
            )
            self.update_checklist_count(count)
            self.update_fields()
            self.check_missing_templates()
            self.add_order()
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Error", str(exc))

    def load_file(self):
        path = filedialog.askopenfilename(
            title="Select HTML or JSON file",
            filetypes=[("Data files", "*.html;*.htm;*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            self.html_content = data
            self.emboss_detected = detect_emboss(data)
            self.temp_path = path
            if path.lower().endswith(".json"):
                parsed = parse_order_json(data)
            else:
                parsed = parse_order(data)
            self.items = parsed.get("items", [])
            self.pairs = parsed.get("pairs", [])
            self.update_order_info(parsed.get("order_info"))
            if parsed.get("art_dir"):
                self.art_dir_var.set(parsed["art_dir"])
            if parsed.get("template_dir"):
                self.template_dir_var.set(parsed["template_dir"])
            if parsed.get("month_dir"):
                self.month_dir_var.set(parsed["month_dir"])
            if parsed.get("order_id"):
                self.order_id_var.set(str(parsed["order_id"]))
            if not self.pairs:
                messagebox.showerror(
                    "Parse error", "Could not extract template / art IDs."
                )
            if not self.items:
                messagebox.showerror("Error", "No order data found")
                return
            self.index = 0
            count = populate_pairs(
                self.pair_frame,
                self.pair_vars,
                self.items,
                self.pairs,
                self.foil_vars,
                self.emboss_vars,
                self.emboss_detected,
            )
            self.update_checklist_count(count)
            self.update_fields()
            self.check_missing_templates()
            self.add_order()
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Error", str(exc))

    def fetch_vista_orders(self):
        """Fetch the work queue and populate order IDs for the Vista company."""
        if not self.queue_page_var.get():
            messagebox.showerror("Error", "Queue page URL required")
            return
        try:
            if not self.logged_in_queue:
                self.login_queue()
            headers = get_queue_headers(self.queue_login_url_var.get())
            page_url = build_queue_url(
                self.queue_login_url_var.get(), self.queue_page_var.get()
            )
            resp = self.queue_session.get(page_url, headers=headers, timeout=30)
            resp.raise_for_status()
            ids = parse_queue(resp.text)
            if not ids:
                messagebox.showinfo("Info", "No Vista orders found")
                return
            existing = set(re.findall(r"\d+", self.ids_text.get("1.0", tk.END)))
            new_ids = [i for i in ids if i not in existing]
            if new_ids:
                if existing:
                    self.ids_text.insert(tk.END, "\n" + "\n".join(new_ids))
                else:
                    self.ids_text.insert(tk.END, "\n".join(new_ids))
                self.on_order_id_change()
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Error", str(exc))

    def prev_item(self):
        current_items = self.items if self.items else self.batch_items
        if current_items and self.index > 0:
            self.index -= 1
            self.update_fields()

    def next_item(self):
        current_items = self.items if self.items else self.batch_items
        if current_items and self.index < len(current_items) - 1:
            self.index += 1
            self.update_fields()

    def save_json(self):
        items_src = self.batch_items if self.batch_items else self.items
        pairs_src = self.batch_pairs if self.batch_pairs else self.pairs
        if not items_src:
            messagebox.showerror("Error", "No order data fetched")
            return
        # Update current item with any edits
        cur = items_src[self.index]
        for key, txt in self.fields.items():
            cur[key] = txt.get("1.0", tk.END).strip()
        items = self.get_selected_items()
        pairs_data = []
        for idx, it in enumerate(items):
            art_id = ""
            template = ""
            if pairs_src and idx < len(pairs_src):
                art_id = pairs_src[idx].get("art_id", "")
                template = pairs_src[idx].get("template", "")
            art_root = it.get("art_dir", self.art_dir_var.get())
            temp_root = it.get("template_dir", self.template_dir_var.get())
            month_root = it.get("month_dir", self.month_dir_var.get())
            order_id = it.get("order_id", self.order_id_var.get())
            art_path = find_art_file(art_root, art_id, month_root, order_id)
            temp_path = find_template_file(temp_root, template)
            paper = extract_paper_type(temp_path)
            lam = it.get("lamType", "") or detect_laminate(it.get("info", ""))
            if not lam and is_coffee_sleeve(template):
                lam = "Uncoated"
            it["paperType"] = paper
            pairs_data.append(
                {
                    "art_id": art_id,
                    "template": template,
                    "art_path": art_path,
                    "template_path": temp_path,
                    "paperType": paper,
                    "lamType": lam,
                }
            )
        save_order_data(
            {
                "items": items,
                "pairs": pairs_data,
                "art_dir": self.art_dir_var.get(),
                "template_dir": self.template_dir_var.get(),
                "month_dir": self.month_dir_var.get(),
                "order_id": self.order_id_var.get(),
                "show_summary": self.summary_var.get(),
                "diagnostic": self.diagnostic_var.get(),
                "preserve_color_profile": self.preserve_color_var.get(),
                "order_info": {
                    "order_id": self.order_info_vars["order_id"].get(),
                    "company": self.order_info_vars["company"].get(),
                    "created_by": self.order_info_vars["sales_rep"].get(),
                },
            }
        )
        self.save_settings()
        messagebox.showinfo("Saved", "order_data.json saved")

    def save_html(self):
        if not self.html_content:
            messagebox.showerror("Error", "No HTML downloaded or loaded")
            return
        path = filedialog.asksaveasfilename(
            title="Save HTML",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.html_content)
            messagebox.showinfo("Saved", f"HTML saved to {path}")
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Error", str(exc))

    def get_selected_items(self) -> list[dict]:
        items_src = self.items if self.items else self.batch_items
        if not self.pair_vars:
            return items_src
        selected = []
        for item, var in zip(items_src, self.pair_vars):
            if var.get():
                selected.append(item)
        return selected

    def get_illustrator_path(self) -> str:
        path = self.ill_path_var.get()
        if not Path(path).exists():
            chosen = filedialog.askopenfilename(title="Select Illustrator executable")
            if chosen:
                self.ill_path_var.set(chosen)
                path = chosen
        return path

    def browse_illustrator(self):
        chosen = filedialog.askopenfilename(title="Select Illustrator executable")
        if chosen:
            self.ill_path_var.set(chosen)
            self.save_settings()

    def browse_art_dir(self):
        chosen = filedialog.askdirectory(title="Select art folder")
        if chosen:
            self.art_dir_var.set(chosen)
            self.save_settings()

    def browse_template_dir(self):
        chosen = filedialog.askdirectory(title="Select template folder")
        if chosen:
            self.template_dir_var.set(chosen)
            self.save_settings()

    def browse_month_dir(self):
        chosen = filedialog.askdirectory(title="Select month folder")
        if chosen:
            self.month_dir_var.set(chosen)
            self.save_settings()

    def browse_art_server(self):
        chosen = filedialog.askdirectory(title="Select Art Server folder")
        if chosen:
            self.art_server_var.set(chosen)
            self.save_settings()

    def browse_gdrive(self):
        chosen = filedialog.askdirectory(title="Select Google Drive folder")
        if chosen:
            self.gdrive_var.set(chosen)
            self.save_settings()

    def open_art_dirs(self):
        """Open all detected artwork directories and arrange them."""
        paths: set[str] = set()
        items = self.items if self.items else self.batch_items
        pairs = self.pairs if self.pairs else self.batch_pairs
        count = max(len(items), len(pairs))
        for i in range(count):
            item = items[i] if i < len(items) else {}
            pair = pairs[i] if i < len(pairs) else {}
            art_root = item.get("art_dir", self.art_dir_var.get())
            month_dir = item.get("month_dir", self.month_dir_var.get())
            order_id = item.get("order_id", self.order_id_var.get())
            art_id = pair.get("art_id", "")
            name_hint = sanitize_filename_base(os.path.splitext(item.get("filename", ""))[0])
            path = find_art_file(art_root, art_id, month_dir, order_id, name_hint)
            dir_path = ""
            if path:
                dir_path = os.path.dirname(path)
            else:
                potential = os.path.join(month_dir, str(order_id), "art")
                if os.path.isdir(potential):
                    dir_path = potential
                elif art_root:
                    dir_path = art_root
            if dir_path and os.path.isdir(dir_path):
                paths.add(dir_path)
        for p in sorted(paths):
            self.open_directory(p)
        self._arrange_windows(list(paths))

    def move_art_to_art_folders(self):
        """Create missing 'art' folders and move art files into them."""
        month_root = self.month_dir_var.get().strip()
        if not month_root:
            messagebox.showerror("Error", "Set month folder first")
            return
        items = self.items if self.items else self.batch_items
        moved = 0
        seen: set[str] = set()
        for it in items:
            order_id = str(it.get("order_id", self.order_id_var.get())).strip()
            if not order_id or order_id in seen:
                continue
            seen.add(order_id)
            order_dir = os.path.join(month_root, order_id)
            moved += move_art_to_folder(order_dir)
        messagebox.showinfo(
            "Move Art",
            f"Moved {moved} file{'s' if moved != 1 else ''} into art folders.",
        )

    def _arrange_windows(self, paths: list[str]):
        """Arrange folder windows in a grid if pygetwindow is available."""
        if not gw:
            return
        titles = [os.path.basename(p).lower() for p in paths]
        windows = []
        start = time.time()
        while time.time() - start < 5:
            for win in gw.getAllWindows():
                title = (win.title or "").lower()
                for name in titles:
                    if name and name in title and win not in windows:
                        windows.append(win)
                        break
            if len(windows) >= len(paths):
                break
            time.sleep(0.2)
        if not windows:
            return
        root = tk.Tk()
        root.withdraw()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        cols = math.ceil(math.sqrt(len(windows)))
        rows = math.ceil(len(windows) / cols)
        w = sw // cols
        h = sh // rows
        for i, win in enumerate(windows):
            try:
                win.resizeTo(w, h)
                win.moveTo((i % cols) * w, (i // cols) * h)
            except Exception:
                continue

    def open_in_acrobat(self, path: str):
        """Open ``path`` with Adobe Acrobat if available."""
        if not path:
            return
        try:
            if sys.platform.startswith("darwin"):
                subprocess.Popen(["open", "-a", "Adobe Acrobat", path])
            elif os.name == "nt":
                acro = os.getenv(
                    "ACROBAT_EXE",
                    r"C:\\Program Files\\Adobe\\Acrobat DC\\Acrobat\\Acrobat.exe",
                )
                subprocess.Popen([acro, path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open in Acrobat: {exc}")

    def open_in_illustrator(self, path: str):
        """Open ``path`` with Adobe Illustrator."""
        if not path:
            return
        path = str(Path(path).resolve())
        ill = self.get_illustrator_path()
        if not ill:
            return
        try:
            subprocess.Popen([ill, path])
        except Exception as exc:
            messagebox.showerror(
                "Error", f"Could not open in Illustrator: {exc}"
            )

    def open_directory(self, path: str):
        """Open a folder in the system file manager."""
        if not path:
            return
        try:
            if sys.platform.startswith("darwin"):
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open directory: {exc}")



    def add_order(self):
        if not self.items:
            messagebox.showerror("Error", "No order data fetched")
            return
        order_id = self.order_id_var.get().strip() or f"Order{len(self.batch_orders)+1}"
        company = self.order_info_vars["company"].get()
        sales_rep = self.order_info_vars["sales_rep"].get()
        self.batch_orders.append(order_id)
        for it in self.items:
            item = it.copy()
            item["order_id"] = order_id
            item["company"] = company
            if sales_rep:
                item["created_by"] = sales_rep
            item["art_dir"] = self.art_dir_var.get()
            item["template_dir"] = self.template_dir_var.get()
            item["month_dir"] = self.month_dir_var.get()
            self.batch_items.append(item)
        for p in self.pairs:
            pair = p.copy()
            pair["order_id"] = order_id
            pair["company"] = company
            if sales_rep:
                pair["created_by"] = sales_rep
            self.batch_pairs.append(pair)
        self.update_batch_display()
        count = populate_pairs(
            self.pair_frame,
            self.pair_vars,
            self.batch_items,
            self.batch_pairs,
            self.foil_vars,
            self.emboss_vars,
            self.emboss_detected,
        )
        self.update_checklist_count(count)
        self.items = []
        self.pairs = []
        self.index = 0
        self.update_fields()

    def update_batch_display(self):
        self.order_list.config(state="normal")
        self.order_list.delete(0, tk.END)
        for oid in self.batch_orders:
            self.order_list.insert(tk.END, oid)
        self.order_list.config(state="disabled")

    def clear_batch(self):
        self.batch_orders.clear()
        self.batch_items.clear()
        self.batch_pairs.clear()
        self.update_batch_display()
        count = populate_pairs(
            self.pair_frame,
            self.pair_vars,
            self.items,
            self.pairs,
            self.foil_vars,
            self.emboss_vars,
            self.emboss_detected,
        )
        self.update_checklist_count(count)
        self.update_fields()
        self.update_order_info()
        self.item_table.delete(*self.item_table.get_children())
        self.ids_text.delete("1.0", tk.END)

    def check_art_server(self):
        path = self.art_server_var.get()
        if os.path.isdir(path):
            self.art_server_status.config(text="Connected", fg="green")
            self.log_message(f"Art Server connected: {path}")
        else:
            self.art_server_status.config(text="Disconnected", fg="red")
            self.log_message("Art Server disconnected")
            messagebox.showinfo(
                "Help",
                "Art Server path needed. Enter a valid directory in the Settings tab.",
            )

    def check_gdrive(self):
        path = self.gdrive_var.get()
        if os.path.isdir(path):
            self.gdrive_status.config(text="Connected", fg="green")
            self.log_message(f"Google Drive connected: {path}")
        else:
            self.gdrive_status.config(text="Disconnected", fg="red")
            self.log_message("Google Drive disconnected")
            messagebox.showinfo(
                "Help",
                "Google Drive path needed. Enter a valid directory in the Settings tab.",
            )

    def disconnect_art_server(self):
        self.art_server_var.set("")
        self.art_server_status.config(text="Disconnected", fg="red")
        self.save_settings()

    def disconnect_gdrive(self):
        self.gdrive_var.set("")
        self.gdrive_status.config(text="Disconnected", fg="red")
        self.save_settings()

    def check_chat_api(self):
        """Test the ChatGPT API connection."""
        key = self.chat_api_key_var.get().strip()
        if not key:
            self.chat_status.config(text="Disconnected", fg="red")
            self.log_message("ChatGPT API key required")
            messagebox.showerror("Error", "ChatGPT API key required")
            return
        url = self.chat_api_url_var.get().strip() or CHAT_API_URL
        if not url.rstrip("/").endswith("/v1"):
            url = url.rstrip("/") + "/v1"
        self.log_message("Testing ChatGPT connection")
        try:
            client = openai.OpenAI(api_key=key, base_url=url)
            client.models.list()
            self.chat_client = client
            self.chat_status.config(text="Connected", fg="green")
            self.log_message("ChatGPT connected")
            self.save_settings()
        except Exception as exc:
            self.chat_client = None
            self.chat_status.config(text="Failed", fg="red")
            self.log_message(f"ChatGPT error: {exc}")
            messagebox.showerror("Error", f"ChatGPT connection failed: {exc}")

    def disconnect_chat_api(self):
        self.chat_client = None
        self.chat_status.config(text="Disconnected", fg="red")
        self.save_settings()

    def update_chat_status(self):
        if self.chat_client:
            self.chat_status.config(text="Connected", fg="green")
        else:
            self.chat_status.config(text="Disconnected", fg="red")

    def logout_queue(self):
        """Reset the session for the work queue site."""
        self.queue_session = requests.Session()
        self.logged_in_queue = False
        self.queue_login_status.config(text="Not logged in", fg="red")
        self.log_message("Queue logout")
        self.save_settings()

    def logout(self):
        self.session = requests.Session()
        self.logged_in = False
        self.login_status.config(text="Not logged in", fg="red")
        self.log_message("Logged out")
        self.save_settings()

    def login(self):
        self.login_log.config(state="normal")
        self.login_log.delete("1.0", tk.END)
        self.login_log.config(state="disabled")
        self.log_message("Starting login")
        try:
            if not self.login_url_var.get():
                self.log_message("Login URL required")
                messagebox.showerror("Error", "Login URL required")
                return
            headers = {"User-Agent": "Mozilla/5.0"}
            self.log_message("Fetching login page")
            resp_get = self.session.get(self.login_url_var.get(), headers=headers, timeout=10)
            self.log_message(f"Fetched login page: HTTP {resp_get.status_code}")

            action_url = self.login_url_var.get()
            method = "post"
            payload = {}
            try:
                soup = BeautifulSoup(resp_get.text, "html.parser")
                form = soup.find("form")
                if form:
                    action_url = urljoin(self.login_url_var.get(), form.get("action", action_url))
                    method = form.get("method", "post").lower()
                    for inp in form.find_all("input"):
                        name = inp.get("name")
                        if not name:
                            continue
                        t = inp.get("type", "text").lower()
                        val = inp.get("value", "")
                        if t in ("text", "email") and not payload.get(name):
                            val = self.username_var.get()
                        elif t == "password":
                            val = self.password_var.get()
                        payload[name] = val
            except Exception as parse_exc:
                self.log_message(f"Error parsing form: {parse_exc}")
                payload = {
                    "username": self.username_var.get(),
                    "password": self.password_var.get(),
                }

            self.log_message("Posting credentials")
            if method == "get":
                resp = self.session.get(action_url, params=payload, headers=headers, timeout=10)
            else:
                resp = self.session.post(action_url, data=payload, headers=headers, timeout=10)
            self.log_message(f"Received HTTP {resp.status_code}")
            resp.raise_for_status()
            with open(APP_DIR / "login_response.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
            self.logged_in = True
            self.login_status.config(text="Logged in", fg="green")
            self.log_message("Login successful")
            self.save_settings()
        except Exception as exc:
            traceback.print_exc()
            self.logged_in = False
            self.login_status.config(text="Login failed", fg="red")
            self.log_message(f"Error: {exc}")
            messagebox.showerror("Error", f"Login failed: {exc}")
        finally:
            # Show current connection status for storage locations
            self.check_art_server()
            self.check_gdrive()

    def login_queue(self):
        """Log in to the work queue site using stored credentials."""
        self.login_log.config(state="normal")
        self.login_log.delete("1.0", tk.END)
        self.login_log.config(state="disabled")
        self.log_message("Starting queue login")
        try:
            if not self.queue_login_url_var.get():
                self.log_message("Queue login URL required")
                messagebox.showerror("Error", "Queue login URL required")
                return

            headers = get_queue_headers(self.queue_login_url_var.get())

            self.log_message("Fetching queue login page")
            resp_get = self.queue_session.get(
                self.queue_login_url_var.get(), headers=headers, timeout=10
            )
            self.log_message(
                f"Fetched queue login page: HTTP {resp_get.status_code}"
            )
            resp_get.raise_for_status()

            action_url, method, payload = parse_login_form(
                resp_get.text,
                self.queue_login_url_var.get(),
                self.queue_username_var.get(),
                self.queue_password_var.get(),
            )

            self.log_message(
                f"Posting to {action_url} with fields {list(payload.keys())}"
            )
            if method == "get":
                resp = self.queue_session.get(
                    action_url, params=payload, headers=headers, timeout=10
                )
            else:
                post_headers = dict(headers)
                post_headers["Content-Type"] = "application/x-www-form-urlencoded"
                resp = self.queue_session.post(
                    action_url, data=payload, headers=post_headers, timeout=10
                )
            self.log_message(f"Queue login response: HTTP {resp.status_code}")
            resp.raise_for_status()
            self.logged_in_queue = True
            self.queue_login_status.config(text="Logged in", fg="green")
            if any(w in resp.text.lower() for w in ["invalid", "error", "login"]):
                self.log_message("Login response may indicate failure")
            else:
                self.log_message("Queue login successful")
            self.save_settings()
        except Exception as exc:
            traceback.print_exc()
            self.logged_in_queue = False
            self.queue_login_status.config(text="Login failed", fg="red")
            self.log_message(f"Queue error: {exc}")
            messagebox.showerror("Error", f"Queue login failed: {exc}")

    def run_illustrator(self):
        self.sample_copy_info.clear()
        items_src = self.items if self.items else self.batch_items
        pairs_src = self.pairs if self.items else self.batch_pairs
        if not items_src:
            messagebox.showerror("Error", "No order data fetched")
            return
        items = self.get_selected_items()
        if not items:
            messagebox.showerror("Error", "No pairs selected")
            return
        # Update current item edits
        cur = items_src[self.index]
        for key, txt in self.fields.items():
            cur[key] = txt.get("1.0", tk.END).strip()

        pairs_data = []
        pair_orders = []
        flat_paths = []
        flat_info: list[tuple[str, str, int, str, str, str, str, str]] = []
        order_counts: dict[str, int] = {}
        for idx, it in enumerate(items):
            art_id = ""
            template = ""
            if pairs_src and idx < len(pairs_src):
                art_id = pairs_src[idx].get("art_id", "")
                template = pairs_src[idx].get("template", "")
                order_id = pairs_src[idx].get("order_id", it.get("order_id", self.order_id_var.get()))
            else:
                order_id = it.get("order_id", self.order_id_var.get())
            art_root = it.get("art_dir", self.art_dir_var.get())
            temp_root = it.get("template_dir", self.template_dir_var.get())
            month_root = it.get("month_dir", self.month_dir_var.get())
            art_path = find_art_file(art_root, art_id, month_root, order_id)
            qty = get_item_quantity(it)
            sample = qty == 11
            temp_path = find_template_file(temp_root, template, sample=sample)
            paper = extract_paper_type(temp_path)
            lam = it.get("lamType", "") or detect_laminate(it.get("info", ""))
            if not lam and is_coffee_sleeve(template):
                lam = "Uncoated"
            it["paperType"] = paper
            # Determine expected flat PDF path for review
            filename_base = sanitize_filename_base(os.path.splitext(it.get("filename", ""))[0])
            flat_path = ""
            if art_path and filename_base:
                dest_root = os.path.dirname(os.path.dirname(art_path))
                folder = "--DO NOT USE - PRINT--" if self.diagnostic_var.get() else "print"
                flat_path = os.path.join(dest_root, folder, f"{filename_base}_flat_{paper}.pdf")
                flat_paths.append(flat_path)
                order_counts[order_id] = order_counts.get(order_id, 0) + 1
                glue = it.get("gluetab", "")
                flat_info.append(
                    (
                        flat_path,
                        order_id,
                        order_counts[order_id],
                        art_id,
                        glue,
                        template,
                        lam,
                        art_path,
                    )
                )
                if sample:
                    cut_src = cut_file_for_template(temp_path)
                    self.sample_copy_info.append((cut_src, os.path.join(dest_root, folder)))
            pairs_data.append({
                "art_id": art_id,
                "template": template,
                "art_path": art_path,
                "template_path": temp_path,
                "qty": qty,
                "paperType": paper,
                "lamType": lam,
                "order_id": order_id,
            })
            pair_orders.append(order_id)

        self.pending_flat_paths = [p for p in flat_paths if p]
        self.pending_flat_info = [
            (p, oid, num, aid, glue, templ, lam, art_path)
            for (p, oid, num, aid, glue, templ, lam, art_path) in flat_info
            if p
        ]

        save_order_data(
            {
                "items": items,
                "pairs": pairs_data,
                "art_dir": self.art_dir_var.get(),
                "template_dir": self.template_dir_var.get(),
                "month_dir": self.month_dir_var.get(),
                "order_id": self.order_id_var.get(),
                "show_summary": self.summary_var.get(),
                "diagnostic": self.diagnostic_var.get(),
                "preserve_color_profile": self.preserve_color_var.get(),
            }
        )
        self.save_settings()
        if self.html_content:
            save_order_html(self.html_content)

        loader = LoadingWindow(self.root, items, pair_orders)
        self.run_start_time = None

        def worker():
            try:
                self.root.withdraw()
                loader.update_status("Launching Illustrator...")
                def progress_hook(msg: str):
                    if self.run_start_time is None:
                        self.run_start_time = time.time()
                        self.root.after(0, self.update_timer)
                    self.root.after(0, loader.update_status, msg)

                launch_illustrator(
                    self.get_illustrator_path(),
                    progress_hook,
                )
            except Exception as exc:
                traceback.print_exc()
                self.root.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                end_time = time.time()
                total = end_time - self.run_start_time if self.run_start_time else 0
                record_run_history(total)
                self.root.after(0, loader.close)
                self.root.after(0, self.root.deiconify)
                self.root.after(0, self.copy_cut_files)
                self.root.after(0, lambda: write_paper_summary(pairs_data))
                self.root.after(0, lambda: self.total_time_var.set(f"Total time: {int(total)}s"))
                self.run_start_time = None
                if self.review_flats_var.get():
                    self.root.after(0, lambda: self.review.start_flat_review(self.pending_flat_info))

        threading.Thread(target=worker, daemon=True).start()


def main():
    try:
        root = ctk.CTk()
    except Exception:
        root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_exit)
    root.mainloop()


# PyInstaller build note:
#   Windows:
#       pyinstaller --onefile --add-data "template_creator.jsx;." order_gui.py
#   Linux/macOS:
#       pyinstaller --onefile --add-data "template_creator.jsx:." order_gui.py

if __name__ == "__main__":
    main()

