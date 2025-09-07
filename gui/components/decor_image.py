"""Decorative bug image helper extracted from tk_qso_form_clean.

Function: add_decorative_bug_image(parent, row, assets_dir)
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

try:  # Optional Pillow
    from PIL import Image, ImageTk  # type: ignore  # noqa: F401
except (ImportError, OSError):
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


def add_decorative_bug_image(parent, row: int, assets_dir: Path) -> None:
    """Place a decorative bug image (if available) or a helper message.

    Looks for ``bug.png`` first, then ``bug.jpg`` inside ``assets_dir``.
    Resizes via Pillow if present; falls back to tk.PhotoImage for PNG/GIF.
    """
    primary = assets_dir / "bug.png"
    fallback = assets_dir / "bug.jpg"
    img_path = primary if primary.exists() else (fallback if fallback.exists() else None)

    max_w, max_h = 200, 150
    bug_img = None

    if img_path and Image and ImageTk:  # Pillow path
        try:
            with Image.open(img_path) as im:  # type: ignore[attr-defined]
                im.thumbnail((max_w, max_h))
                bug_img = ImageTk.PhotoImage(im)  # type: ignore[attr-defined]
        except (OSError, ValueError):
            bug_img = None
    elif img_path and img_path.suffix.lower() in {".png", ".gif"}:
        try:
            bug_img = tk.PhotoImage(file=str(img_path))
        except (OSError, ValueError):
            bug_img = None

    deco_frame = ttk.Frame(parent)
    deco_frame.grid(row=row, column=0, columnspan=2, sticky="sw", padx=6, pady=(8, 0))
    if bug_img is not None:
        # Hold a reference on the frame to avoid garbage collection
        deco_frame.bug_img_ref = bug_img
        ttk.Label(deco_frame, image=bug_img).pack(anchor="w")
    else:
        msg = "Add 'assets/bug.png' (or bug.jpg). PNG loads without Pillow; JPG requires Pillow."
        ttk.Label(
            deco_frame,
            text=msg,
            foreground="gray",
            font=("Arial", 8, "italic"),
            wraplength=300,
            justify="left",
        ).pack(anchor="w")


__all__ = ["add_decorative_bug_image"]
