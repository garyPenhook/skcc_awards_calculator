"""Space Weather panel component extracted from tk_qso_form_clean.

Provides a SpaceWeatherPanel class that can be embedded in any Tk parent
and a helper refresh scheduler. Keeps UI + fetch/parsing logic separate
from the main QSO form to reduce complexity and silences many lint issues.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from utils.space_weather import summarize_for_ui_minimal


class SpaceWeatherPanel(ttk.LabelFrame):
    """A small panel displaying current space weather metrics.

    Metrics shown (simplified):
        - Kp index (geomagnetic)
        - Solar Flux Index (SFI)
        - Sunspot Number (SSN)
        - A index
        - Last updated timestamp
    """

    REFRESH_INTERVAL_MS = 60_000

    def __init__(self, master: tk.Widget, *, auto_start: bool = True):  # noqa: D401
        super().__init__(master, text="Space Weather (NOAA SWPC)", padding=10)
        self.kp_var = tk.StringVar(value="Kp —")
        self.sfi_var = tk.StringVar(value="SFI —")
        self.ssn_var = tk.StringVar(value="SSN —")
        self.aindex_var = tk.StringVar(value="A —")
        self.updated_var = tk.StringVar(value="Updated —")

        row = ttk.Frame(self)
        row.pack(fill="x")
        self._kp_label = ttk.Label(
            row,
            textvariable=self.kp_var,
            font=("Consolas", 10, "bold"),
            foreground="green",
        )
        self._kp_label.pack(side=tk.LEFT, padx=(0, 15))
        self._sfi_label = ttk.Label(row, textvariable=self.sfi_var)
        self._sfi_label.pack(side=tk.LEFT, padx=(0, 15))
        self._ssn_label = ttk.Label(row, textvariable=self.ssn_var)
        self._ssn_label.pack(side=tk.LEFT, padx=(0, 15))
        self._a_label = ttk.Label(row, textvariable=self.aindex_var)
        self._a_label.pack(side=tk.LEFT, padx=(0, 15))
        self._upd_label = ttk.Label(row, textvariable=self.updated_var, foreground="gray")
        self._upd_label.pack(side=tk.LEFT)

        ttk.Button(self, text="Refresh", command=self.refresh_async).pack(side=tk.RIGHT)

        # Tooltips (optional lightweight approach)
        self._add_tooltip(self._kp_label, "Kp (geomagnetic activity): lower is better")
        self._add_tooltip(self._sfi_label, "SFI: higher generally favors higher bands")
        self._add_tooltip(self._ssn_label, "Sunspot Number (SSN): indicates solar activity level")
        self._add_tooltip(self._a_label, "A-index: 24h geomagnetic activity; lower is better")

        if auto_start:
            # initial fetch
            self.refresh_async()

    # ---------------- Public API -----------------
    def refresh_async(self):
        """Refresh space weather values in a background thread and update UI."""

        def worker():
            try:
                kp_text, sfi_text, ssn_text, a_text, updated = summarize_for_ui_minimal()
            except (ValueError, OSError):
                kp_text, sfi_text, ssn_text, a_text, updated = (
                    "Kp —",
                    "SFI —",
                    "SSN —",
                    "A —",
                    "Updated —",
                )
            self.after(
                0,
                lambda: self._apply_update(kp_text, sfi_text, ssn_text, a_text, updated),
            )

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Internal helpers -----------------
    def _apply_update(
        self,
        kp_text: str,
        sfi_text: str,
        ssn_text: str,
        a_text: str,
        updated: str,
    ) -> None:
        self.kp_var.set(kp_text)
        self.sfi_var.set(sfi_text)
        self.ssn_var.set(ssn_text)
        self.aindex_var.set(a_text)
        self.updated_var.set(updated)
        self._color_code()
        # schedule next refresh
        self.after(self.REFRESH_INTERVAL_MS, self.refresh_async)

    def _color_code(self) -> None:
        import re

        # Kp
        kp_val = None
        m = re.search(r"Kp\s+(\d+(?:\.\d)?)", self.kp_var.get())
        if m:
            try:
                kp_val = float(m.group(1))
            except ValueError:
                kp_val = None
        if kp_val is None:
            self._kp_label.configure(foreground="gray")
        elif kp_val < 4:
            self._kp_label.configure(foreground="green")
        elif kp_val < 6:
            self._kp_label.configure(foreground="orange")
        else:
            self._kp_label.configure(foreground="red")

        # A-index
        a_val = None
        m = re.search(r"\bA\s+(\d+(?:\.\d)?)", self.aindex_var.get())
        if m:
            try:
                a_val = float(m.group(1))
            except ValueError:
                a_val = None
        if a_val is None:
            self._a_label.configure(foreground="gray")
        elif a_val <= 10:
            self._a_label.configure(foreground="green")
        elif a_val <= 20:
            self._a_label.configure(foreground="orange")
        else:
            self._a_label.configure(foreground="red")

        # SSN coloring (simple heuristic)
        ssn_val = None
        m = re.search(r"SSN\s+(\d+)", self.ssn_var.get())
        if m:
            try:
                ssn_val = int(m.group(1))
            except ValueError:
                ssn_val = None
        if ssn_val is None:
            self._ssn_label.configure(foreground="gray")
        elif ssn_val < 50:
            self._ssn_label.configure(foreground="orange")
        elif ssn_val < 100:
            self._ssn_label.configure(foreground="green")
        else:
            self._ssn_label.configure(foreground="blue")

    # Simple tooltip (kept local)
    def _add_tooltip(self, widget: tk.Widget, text: str) -> None:  # noqa: D401
        try:
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.withdraw()
            lbl = ttk.Label(tip, text=text, background="#ffffe0", relief="solid", borderwidth=1)
            lbl.pack(ipadx=4, ipady=2)

            def show_tip(_e):
                x = widget.winfo_pointerx() + 12
                y = widget.winfo_pointery() + 12
                tip.wm_geometry(f"+{x}+{y}")
                tip.deiconify()

            def hide_tip(_e):
                tip.withdraw()

            widget.bind("<Enter>", show_tip)
            widget.bind("<Leave>", hide_tip)
        except tk.TclError:
            pass


__all__ = ["SpaceWeatherPanel"]
