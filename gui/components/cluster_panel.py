"""Cluster (RBN) integration extracted from tk_qso_form_clean.

Provides ClusterController to manage connection and spot handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable
import tkinter as tk
from tkinter import simpledialog, ttk

from utils.cluster_client import SKCCClusterClient, ClusterSpot


@dataclass
class ClusterUIRefs:
    connect_button: ttk.Button
    status_var: tk.StringVar
    status_label: ttk.Label
    spots_tree: ttk.Treeview
    set_status: Callable[[str, str, int], None]
    roster_lookup: Callable[[str], Optional[dict]]


class ClusterController:
    def __init__(self, parent_frame, ui: ClusterUIRefs):
        self.parent = parent_frame
        self.ui = ui
        self.client: Optional[SKCCClusterClient] = None

    # Public API -----------------------------------------------------
    def toggle(self):
        if self.client and self.client.connected:
            self._disconnect()
        else:
            self._connect_prompt()

    def handle_double_click(self, form_callback: Callable[[str, str, str], None]):
        try:
            item = self.ui.spots_tree.selection()[0]
            values = self.ui.spots_tree.item(item, "values")
        except (IndexError, tk.TclError):
            return
        if values:
            try:
                callsign, freq, band = values[1], values[4], values[5]
                form_callback(callsign, freq, band)
                self._safe_status(f"From spot: {callsign} @ {freq} MHz ({band})", "blue")
            except (tk.TclError, ValueError):
                return

    # Internal -------------------------------------------------------
    def _connect_prompt(self):
        callsign = simpledialog.askstring(
            "RBN Connection",
            (
                "Enter your callsign (you may append -SKCC / -TEST etc.; "
                "leave suffix off for plain call):"
            ),
        )
        if not callsign:
            return
        callsign = callsign.upper().strip()
        self.client = SKCCClusterClient(callsign, self._on_new_spot, include_clubs=None)
        if self.client.connect():
            self.ui.connect_button.config(text="Disconnect")
            self.ui.status_var.set(f"Connected as {callsign}")
            self.ui.status_label.config(foreground="green")
            self._safe_status(f"RBN connected as {callsign}", "green")
        else:
            self.client = None
            self.ui.status_var.set("Connection failed")
            self.ui.status_label.config(foreground="red")
            self._safe_status("RBN connection failed", "red")

    def _disconnect(self):
        if self.client:
            try:
                self.client.disconnect()
            except OSError:
                pass
        self.client = None
        self.ui.connect_button.config(text="Connect to RBN")
        self.ui.status_var.set("Disconnected")
        self.ui.status_label.config(foreground="red")
        self._safe_status("RBN disconnected", "orange")

    def _on_new_spot(self, spot: ClusterSpot):
        # Thread-safe UI add
        self.parent.after(0, self._add_spot, spot)

    def _add_spot(self, spot: ClusterSpot):
        try:
            time_str = spot.time_utc.strftime("%H:%M")
            freq_str = f"{spot.frequency:.3f}"
            snr_str = f"{spot.snr}dB" if spot.snr else ""

            # Remove existing entry for same call (keep newest)
            for child in self.ui.spots_tree.get_children():
                vals = self.ui.spots_tree.item(child, "values")
                if vals and len(vals) > 2 and vals[1] == spot.callsign:
                    self.ui.spots_tree.delete(child)

            # Lookup SKCC membership
            skcc_num = ""
            try:
                info = self.ui.roster_lookup(spot.callsign)
            except (KeyError, AttributeError):
                info = None
            if info and info.get("number"):
                skcc_num = info["number"]

            clubs_display = spot.clubs or ""
            try:
                clubs_set = {c.strip().upper() for c in clubs_display.split(",") if c.strip()}
            except AttributeError:
                clubs_set = set()
            if skcc_num:
                clubs_set.add("SKCC")
            base = ["SKCC"] if "SKCC" in clubs_set else []
            ordered = [*base, *sorted(x for x in clubs_set if x != "SKCC")]
            clubs_display = ", ".join(ordered)

            item = self.ui.spots_tree.insert(
                "",
                0,
                values=(
                    time_str,
                    spot.callsign,
                    skcc_num,
                    clubs_display,
                    freq_str,
                    spot.band,
                    spot.spotter,
                    snr_str,
                ),
            )
            # Keep only last 50
            children = self.ui.spots_tree.get_children()
            if len(children) > 50:
                for ch in children[50:]:
                    self.ui.spots_tree.delete(ch)
            self.ui.spots_tree.see(item)
        except (tk.TclError, ValueError):  # Keep UI resilient
            return

    # Helpers --------------------------------------------------------
    def _safe_status(self, msg: str, color: str):
        try:
            self.ui.set_status(msg, color, 0)
        except (tk.TclError, AttributeError):
            return


__all__ = ["ClusterController", "ClusterUIRefs"]
