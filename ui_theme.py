"""Common GUI theme helpers for the Valis64 tools."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Dimensions and fonts
BUTTON_DIM = (120, 32)
PAD = (8, 8)

TEXT_FONT = ("Segoe UI", 10)
BUTTON_FONT = ("Segoe UI Semibold", 10)

# Light and dark color palettes
LIGHT_COLORS = {
    "background": "#ffffff",
    "foreground": "#000000",
    "button_background": "#e0e0e0",
    "button_foreground": "#000000",
    "accent": "#007acc",
}

DARK_COLORS = {
    "background": "#333333",
    "foreground": "#ffffff",
    "button_background": "#555555",
    "button_foreground": "#ffffff",
    "accent": "#409cff",
}

# Internal palette used by factory helpers
_palette = LIGHT_COLORS.copy()


def _apply_palette(root: tk.Misc, colors: dict) -> None:
    """Configure the root widget using the given color palette."""

    root.configure(bg=colors["background"])
    style = ttk.Style(root)
    style.configure(
        "TFrame",
        background=colors["background"],
    )
    style.configure(
        "TLabel",
        background=colors["background"],
        foreground=colors["foreground"],
        font=TEXT_FONT,
    )
    style.configure(
        "TButton",
        background=colors["button_background"],
        foreground=colors["button_foreground"],
        font=BUTTON_FONT,
        padding=PAD,
    )
    style.map(
        "TButton",
        background=[("active", colors["accent"])],
        foreground=[("active", colors["button_foreground"])],
    )

    # Tk option database fallback for non-ttk widgets
    root.option_add("*Font", TEXT_FONT)
    root.option_add("*Foreground", colors["foreground"])
    root.option_add("*Background", colors["background"])
    root.option_add("*Button.Font", BUTTON_FONT)
    root.option_add("*Button.Background", colors["button_background"])
    root.option_add("*Button.Foreground", colors["button_foreground"])
    root.option_add("*Button.activeBackground", colors["accent"])
    root.option_add("*Button.activeForeground", colors["button_foreground"])


# Public helpers

def apply_light_mode(root: tk.Misc) -> None:
    """Apply the light color palette to ``root``."""

    global _palette
    _palette = LIGHT_COLORS.copy()
    _apply_palette(root, _palette)


def apply_dark_mode(root: tk.Misc) -> None:
    """Apply the dark color palette to ``root``."""

    global _palette
    _palette = DARK_COLORS.copy()
    _apply_palette(root, _palette)


def primary_button(parent: tk.Misc, text: str, command=None, **kw) -> tk.Button:
    """Return a Button using the accent color."""

    return tk.Button(
        parent,
        text=text,
        command=command,
        width=BUTTON_DIM[0],
        font=BUTTON_FONT,
        bg=_palette["accent"],
        fg=_palette["button_foreground"],
        activebackground=_palette["accent"],
        activeforeground=_palette["button_foreground"],
        **kw,
    )


def secondary_button(parent: tk.Misc, text: str, command=None, **kw) -> tk.Button:
    """Return a standard Button using the palette's button color."""

    return tk.Button(
        parent,
        text=text,
        command=command,
        width=BUTTON_DIM[0],
        font=BUTTON_FONT,
        bg=_palette["button_background"],
        fg=_palette["button_foreground"],
        activebackground=_palette["accent"],
        activeforeground=_palette["button_foreground"],
        **kw,
    )


__all__ = [
    "BUTTON_DIM",
    "PAD",
    "TEXT_FONT",
    "BUTTON_FONT",
    "LIGHT_COLORS",
    "DARK_COLORS",
    "primary_button",
    "secondary_button",
    "apply_dark_mode",
    "apply_light_mode",
]
