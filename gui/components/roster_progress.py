"""Roster progress dialog component extracted from tk_qso_form_clean.

Provides: RosterProgressDialog
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk


class RosterProgressDialog:
    """Progress dialog for roster updates."""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("W4GNS SKCC Logger - Initializing")
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)

        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame,
            text="W4GNS SKCC Logger",
            font=("Arial", 14, "bold"),
        ).pack(pady=(0, 10))

        self.status_label = ttk.Label(main_frame, text="Checking member roster...")
        self.status_label.pack(pady=5)

        self.progress = ttk.Progressbar(main_frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=10)
        self.progress.start()

        self.detail_label = ttk.Label(main_frame, text="", foreground="gray")
        self.detail_label.pack(pady=5)

        self.status_text = tk.Text(main_frame, height=4, width=50, font=("Consolas", 8))
        self.status_text.pack(fill="both", expand=True, pady=(10, 0))

        self.close_button = ttk.Button(main_frame, text="Close", command=self.close)
        self.close_button.pack_forget()

    def update_status(self, message: str, detail: str = "") -> None:
        if not self.dialog:
            return
        self.status_label.config(text=message)
        if detail:
            self.detail_label.config(text=detail)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        if detail:
            self.status_text.insert(tk.END, f"           {detail}\n")
        self.status_text.see(tk.END)
        self.dialog.update()

    def show_final_status(self, message: str, detail: str = "") -> None:
        if not self.dialog:
            return
        self.update_status(message, detail)
        self.progress.stop()
        self.close_button.pack(pady=(10, 0))

    def close(self) -> None:
        try:
            if getattr(self, "progress", None):
                self.progress.stop()
            if getattr(self, "dialog", None):
                self.dialog.destroy()
                self.dialog = None
        except tk.TclError:
            pass


__all__ = ["RosterProgressDialog"]
