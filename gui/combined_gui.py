"""Unified SKCC Logger + Awards Manager GUI.

This module combines the existing QSO logging form (QSOForm) and the
Awards calculation interface into a single Tkinter window using a
Notebook with two primary tabs: "Logger" and "Awards".

The Awards panel code is adapted from scripts/gui.py (AwardsGUI) and
refactored into an embeddable Frame (AwardsPanel) to avoid creating a
second root window.
"""

from __future__ import annotations

import asyncio
import csv
import json
import queue
import re
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Adjust sys.path early
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.skcc import (  # type: ignore  # noqa: E402
    Member,
    calculate_awards,
    fetch_member_roster,
    parse_adif,
)

from gui.tk_qso_form_clean import QSOForm  # type: ignore  # noqa: E402

# Regex patterns copied from original Awards GUI
ADIF_EXTENSION_PATTERN = re.compile(r"\.(adi|adif)$", re.IGNORECASE)
URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
MEMBER_NUMBER_PATTERN = re.compile(r"^\d+$")
CALLSIGN_PATTERN = re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]$")

APP_TITLE = "SKCC Logger + Awards Manager"
PREFS_PATH = Path.home() / ".skcc_awards" / "user_prefs.json"
MIN_LIVE_ROSTER_MEMBERS = 100
MIN_CSV_COLUMNS = 2


def _load_prefs() -> dict:
    if not PREFS_PATH.is_file():
        return {}
    try:
        with PREFS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):  # pragma: no cover
        return {}
    return {}


def _save_prefs(update: dict) -> None:
    try:
        PREFS_PATH.parent.mkdir(exist_ok=True)
        data = _load_prefs()
        data.update(update)
        data["timestamp"] = datetime.utcnow().isoformat() + "Z"
        with PREFS_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:  # pragma: no cover
        return


class AwardsPanel(ttk.Frame):
    """Embeddable awards calculation panel (adapted from AwardsGUI)."""

    def __init__(self, master: tk.Widget):  # noqa: D401
        super().__init__(master, padding=6)
        self.pack(fill=tk.BOTH, expand=True)

        # State containers (lists start empty until user loads files)
        self.adif_paths: list[Path] = []
        self.members: list[Member] = []
        self._logger_form: QSOForm | None = None  # set via set_logger_form
        self.roster_loaded = False

        self.roster_url_var = tk.StringVar(value="")
        self.enforce_key_var = tk.BooleanVar(value=False)
        self.missing_key_valid_var = tk.BooleanVar(value=True)
        self.enforce_suffix_var = tk.BooleanVar(value=True)

        # Widgets built here
        self._build_widgets()
        self.task_queue: queue.Queue = queue.Queue()
        self.after(150, self._poll_queue)

    # ------------------------------------------------------------------
    # UI BUILD
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Select ADIF file(s) for awards computation.")

        ttk.Button(top, text="Add ADIF", command=self.select_adif).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="Clear ADIF", command=self.clear_adif).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="Load Roster (Live)", command=self.load_roster_live).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(top, text="Load Roster CSV", command=self.load_roster_csv).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(top, text="Compute", command=self.compute).pack(side=tk.LEFT, padx=10)
        # Will be enabled once logger form attached
        self.use_logger_btn = ttk.Button(
            top, text="Use Logger ADIF", command=self.use_logger_adif, state=tk.DISABLED
        )
        self.use_logger_btn.pack(side=tk.LEFT, padx=4)

        opt = ttk.Frame(self)
        opt.pack(fill=tk.X, pady=(4, 0))
        ttk.Checkbutton(opt, text="Enforce key type", variable=self.enforce_key_var).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Checkbutton(opt, text="Missing key OK", variable=self.missing_key_valid_var).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Checkbutton(
            opt,
            text="Enforce SKCC suffix rules",
            variable=self.enforce_suffix_var,
        ).pack(side=tk.LEFT, padx=4)

        # Roster URL entry
        url_row = ttk.Frame(self)
        url_row.pack(fill=tk.X, pady=(2, 2))
        ttk.Label(url_row, text="Roster URL (optional):").pack(side=tk.LEFT)
        url_entry = ttk.Entry(url_row, textvariable=self.roster_url_var, width=60)
        url_entry.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        ttk.Button(url_row, text="Clear", command=lambda: self.roster_url_var.set("")).pack(
            side=tk.LEFT
        )

        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill=tk.X, pady=(2, 4))

        # ADIF list
        adif_frame = ttk.LabelFrame(self, text="ADIF Files", padding=4)
        adif_frame.pack(fill=tk.X, padx=4, pady=4)
        self.adif_list = tk.Listbox(adif_frame, height=4)
        self.adif_list.pack(fill=tk.BOTH, expand=True)

        # Notebook for results
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True)

        # Awards tab
        self.awards_tab = ttk.Frame(self.nb)
        self.nb.add(self.awards_tab, text="Awards")
        self.awards_tree = ttk.Treeview(
            self.awards_tab, columns=("required", "current", "achieved"), show="headings"
        )
        for col, txt, w in [
            ("required", "Required", 80),
            ("current", "Current", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.awards_tree.heading(col, text=txt)
            self.awards_tree.column(col, width=w, anchor=tk.CENTER)
        self.awards_tree.pack(fill=tk.BOTH, expand=True)

        # Endorsements tab
        self.end_tab = ttk.Frame(self.nb)
        self.nb.add(self.end_tab, text="Endorsements")
        self.endorse_tree = ttk.Treeview(
            self.end_tab,
            columns=("category", "value", "current", "required"),
            show="headings",
        )
        for col, txt, w in [
            ("category", "Category", 80),
            ("value", "Value", 100),
            ("current", "Current", 80),
            ("required", "Required", 80),
        ]:
            self.endorse_tree.heading(col, text=txt)
            self.endorse_tree.column(col, width=w, anchor=tk.CENTER)
        self.endorse_tree.pack(fill=tk.BOTH, expand=True)

        # Canadian Maple tab
        self.maple_tab = ttk.Frame(self.nb)
        self.nb.add(self.maple_tab, text="Canadian Maple")
        self.maple_tree = ttk.Treeview(
            self.maple_tab,
            columns=("level", "band", "provinces", "achieved"),
            show="headings",
        )
        for col, txt, w in [
            ("level", "Level", 80),
            ("band", "Band", 80),
            ("provinces", "Provinces", 110),
            ("achieved", "Achieved", 80),
        ]:
            self.maple_tree.heading(col, text=txt)
            self.maple_tree.column(col, width=w, anchor=tk.CENTER)
        self.maple_tree.pack(fill=tk.BOTH, expand=True)

        # DX tab
        self.dx_tab = ttk.Frame(self.nb)
        self.nb.add(self.dx_tab, text="DX")
        self.dx_tree = ttk.Treeview(
            self.dx_tab,
            columns=("type", "threshold", "current", "achieved"),
            show="headings",
        )
        for col, txt, w in [
            ("type", "Type", 110),
            ("threshold", "Threshold", 80),
            ("current", "Current", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.dx_tree.heading(col, text=txt)
            self.dx_tree.column(col, width=w, anchor=tk.CENTER)
        self.dx_tree.pack(fill=tk.BOTH, expand=True)

        # PFX tab
        self.pfx_tab = ttk.Frame(self.nb)
        self.nb.add(self.pfx_tab, text="PFX")
        self.pfx_tree = ttk.Treeview(
            self.pfx_tab,
            columns=("level", "band", "score", "prefixes", "achieved"),
            show="headings",
        )
        for col, txt, w in [
            ("level", "Level", 70),
            ("band", "Band", 70),
            ("score", "Score", 120),
            ("prefixes", "Prefixes", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.pfx_tree.heading(col, text=txt)
            self.pfx_tree.column(col, width=w, anchor=tk.CENTER)
        self.pfx_tree.pack(fill=tk.BOTH, expand=True)

        # Triple Key tab
        self.tk_tab = ttk.Frame(self.nb)
        self.nb.add(self.tk_tab, text="Triple Key")
        self.triple_key_tree = ttk.Treeview(
            self.tk_tab,
            columns=("key_type", "current", "threshold", "progress", "achieved"),
            show="headings",
        )
        for col, txt, w in [
            ("key_type", "Key Type", 140),
            ("current", "Current", 80),
            ("threshold", "Threshold", 80),
            ("progress", "Progress", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.triple_key_tree.heading(col, text=txt)
            self.triple_key_tree.column(col, width=w, anchor=tk.CENTER)
        self.triple_key_tree.pack(fill=tk.BOTH, expand=True)

        # Rag Chew tab
        self.rag_tab = ttk.Frame(self.nb)
        self.nb.add(self.rag_tab, text="Rag Chew")
        self.rag_chew_tree = ttk.Treeview(
            self.rag_tab,
            columns=("level", "band", "minutes", "qsos", "achieved"),
            show="headings",
        )
        for col, txt, w in [
            ("level", "Level", 80),
            ("band", "Band", 60),
            ("minutes", "Minutes", 90),
            ("qsos", "QSOs", 60),
            ("achieved", "Achieved", 80),
        ]:
            self.rag_chew_tree.heading(col, text=txt)
            self.rag_chew_tree.column(col, width=w, anchor=tk.CENTER)
        self.rag_chew_tree.pack(fill=tk.BOTH, expand=True)

        # WAC tab
        self.wac_tab = ttk.Frame(self.nb)
        self.nb.add(self.wac_tab, text="WAC")
        self.wac_tree = ttk.Treeview(
            self.wac_tab,
            columns=("award_type", "band", "continents", "worked", "achieved"),
            show="headings",
        )
        for col, txt, w in [
            ("award_type", "Award Type", 160),
            ("band", "Band", 70),
            ("continents", "Continents", 170),
            ("worked", "Worked", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.wac_tree.heading(col, text=txt)
            self.wac_tree.column(col, width=w, anchor=tk.CENTER)
        self.wac_tree.pack(fill=tk.BOTH, expand=True)

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, pady=(2, 0))
        self.unique_var = tk.StringVar(value="Unique Members Worked: -")
        ttk.Label(bottom, textvariable=self.unique_var, anchor="w").pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # File / roster actions
    # ------------------------------------------------------------------
    def select_adif(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select ADIF files", filetypes=[("ADIF", "*.adi *.adif"), ("All", "*.*")]
        )
        if not paths:
            return
        added = 0
        for p in paths:
            path_obj = Path(p)
            if not ADIF_EXTENSION_PATTERN.search(path_obj.name):
                continue
            if path_obj not in self.adif_paths:
                self.adif_paths.append(path_obj)
                self.adif_list.insert(tk.END, str(path_obj))
                added += 1
        if added:
            self.status_var.set(f"Added {added} ADIF file(s). Total: {len(self.adif_paths)}")
        else:
            self.status_var.set("No new ADIF files added.")

    def clear_adif(self) -> None:
        self.adif_paths.clear()
        self.adif_list.delete(0, tk.END)
        self.status_var.set("ADIF list cleared.")
        _save_prefs({"awards_adif_paths": []})

    def set_logger_form(self, logger_form: QSOForm) -> None:  # type: ignore[name-defined]
        """Attach reference to logger form to allow ADIF import."""
        self._logger_form = logger_form
        self.use_logger_btn.config(state=tk.NORMAL)

    def use_logger_adif(self) -> None:
        lf = getattr(self, "_logger_form", None)
        if not lf or not hasattr(lf, "adif_var"):
            messagebox.showwarning("Logger ADIF", "Logger ADIF not available.")
            return
        path = lf.adif_var.get().strip()
        if not path:
            messagebox.showinfo("Logger ADIF", "Logger has no ADIF file selected yet.")
            return
        p = Path(path)
        if not p.exists():
            messagebox.showerror("Logger ADIF", f"File not found: {p}")
            return
        # Replace current list with this one
        self.clear_adif()
        self.adif_paths.append(p)
        self.adif_list.insert(tk.END, str(p))
        self.status_var.set(f"Using logger ADIF: {p.name}")
        _save_prefs({"awards_adif_paths": [str(p)], "logger_adif_path": str(p)})

    # Direct load for persistence (bypasses file dialog)
    def load_roster_csv_from_path(self, path: Path) -> bool:
        if not path.exists() or not path.is_file():
            return False
        try:
            members = self._read_members_csv(path)
        except RuntimeError:  # invalid CSV
            return False
        self.members = members
        self.roster_loaded = True
        self.status_var.set(f"Loaded {len(members)} members from CSV (restored)")
        _save_prefs({"roster_mode": "csv", "roster_csv_path": str(path)})
        return True

    def load_roster_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Roster CSV", filetypes=[("CSV", "*.csv"), ("All", "*.*")]
        )
        if not path:
            return
        path_obj = Path(path)
        try:
            if not path_obj.exists() or not path_obj.is_file():
                raise ValueError("Invalid CSV path")
            members = self._read_members_csv(path_obj)
            self.members = members
            self.roster_loaded = True
            self.status_var.set(f"Loaded {len(self.members)} members from CSV.")
        except ValueError as e:
            messagebox.showerror("CSV Import Error", str(e))
            self.status_var.set(f"CSV import failed: {e}")

    def load_roster_live(self) -> None:
        # Validate optional custom URL
        custom_url = self.roster_url_var.get().strip()
        if custom_url and not URL_PATTERN.match(custom_url):  # SIM102 combined
            messagebox.showerror("Invalid URL", "Please provide a valid HTTP/HTTPS URL")
            return
        self.status_var.set("Fetching live roster...")
        threading.Thread(target=self._fetch_roster_thread, daemon=True).start()

    def _fetch_roster_thread(self) -> None:
        try:
            custom_url = self.roster_url_var.get().strip() or None
            members = asyncio.run(fetch_member_roster(url=custom_url))
            if not members or len(members) < MIN_LIVE_ROSTER_MEMBERS:  # PLR2004
                raise RuntimeError("Roster fetch returned too few members")
            self.task_queue.put(("roster", members))
        except RuntimeError as e:
            self.task_queue.put(("error", f"Roster fetch failed: {e}"))

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def compute(self) -> None:
        if not self.adif_paths:
            messagebox.showwarning("No ADIF", "Select at least one ADIF file.")
            return
        if not self.members and not self.roster_loaded:
            self.status_var.set("Auto-fetching roster...")
            threading.Thread(target=self._compute_with_live_roster, daemon=True).start()
        else:
            threading.Thread(target=self._compute_thread, daemon=True).start()

    def _compute_with_live_roster(self) -> None:
        try:
            custom_url = self.roster_url_var.get().strip() or None
            self.members = asyncio.run(fetch_member_roster(url=custom_url))
            self.roster_loaded = True
        except RuntimeError as e:
            self.task_queue.put(("error", f"Live roster fetch failed: {e}"))
            return
        self._compute_thread()

    def _compute_thread(self) -> None:
        try:
            adif_contents = []
            for path in self.adif_paths:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    raise RuntimeError(f"Empty ADIF: {path.name}")
                if "<EOR>" not in content and "<eor>" not in content:
                    raise RuntimeError(f"Missing EOR markers: {path.name}")
                adif_contents.append(content)
            qsos = []
            for content in adif_contents:
                qsos.extend(parse_adif(content))
            if not qsos:
                raise RuntimeError("No QSOs parsed from ADIF files")
            result = calculate_awards(
                qsos,
                self.members,
                enforce_key_type=self.enforce_key_var.get(),
                treat_missing_key_as_valid=self.missing_key_valid_var.get(),
                enforce_suffix_rules=self.enforce_suffix_var.get(),
            )
            self.task_queue.put(("result", result))
        except RuntimeError as e:
            self.task_queue.put(("error", f"Calculation failed: {e}"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read_members_csv(self, path: Path) -> list[Member]:
        out: list[Member] = []
        with path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
            try:
                sample = f.read(2048)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                reader = csv.reader(f, dialect)
            except csv.Error:
                f.seek(0)
                reader = csv.reader(f)
            for row in reader:
                if len(row) < MIN_CSV_COLUMNS:  # PLR2004
                    continue
                number_str = row[0].strip()
                call = row[1].strip().upper()
                if not number_str or not MEMBER_NUMBER_PATTERN.match(number_str):
                    continue
                if not call:
                    continue
                try:
                    number = int(number_str)
                except ValueError:
                    continue
                if any(m.number == number or m.call == call for m in out):
                    continue
                out.append(Member(call=call, number=number))
        if not out:
            raise RuntimeError("No valid member rows in CSV")
        return out

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.task_queue.get_nowait()
                self._handle_task_item(item)
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _handle_task_item(self, item) -> None:  # noqa: C901
        kind = item[0]
        if kind == "roster":
            self.members = item[1]
            self.roster_loaded = True
            self.status_var.set(f"Live roster loaded: {len(self.members)} members")
        elif kind == "result":
            result = item[1]
            for tree in (
                self.awards_tree,
                self.endorse_tree,
                self.maple_tree,
                self.dx_tree,
                self.pfx_tree,
                self.triple_key_tree,
                self.rag_chew_tree,
                self.wac_tree,
            ):
                for iid in tree.get_children():
                    tree.delete(iid)
            # Awards
            for a in result.awards:
                self.awards_tree.insert(
                    "",
                    tk.END,
                    values=(a.required, a.current, "Yes" if a.achieved else "No"),
                    text=a.name,
                )
            self.awards_tree.configure(show="tree headings")
            for i, iid in enumerate(self.awards_tree.get_children()):
                self.awards_tree.item(iid, text=result.awards[i].name)
            # Endorsements
            for e in result.endorsements:
                self.endorse_tree.insert(
                    "",
                    tk.END,
                    values=(e.category, e.value, e.current, e.required),
                    text=e.award,
                )
            # Canadian Maple
            for maple in result.canadian_maple_awards:
                band_text = maple.band if maple.band else "All"
                province_text = f"{maple.current_provinces}/{maple.required_provinces}"
                achieved_text = "Yes" if maple.achieved else "No"
                qrp_text = " (QRP)" if getattr(maple, "qrp_required", False) else ""
                level_text = f"{maple.level}{qrp_text}"
                self.maple_tree.insert(
                    "",
                    tk.END,
                    values=(level_text, band_text, province_text, achieved_text),
                    text=maple.name,
                )
            # DX Awards
            for dx in result.dx_awards:
                if dx.current_count > 0 or dx.achieved:
                    type_text = dx.award_type + (" QRP" if dx.qrp_qualified else "")
                    self.dx_tree.insert(
                        "",
                        tk.END,
                        values=(
                            type_text,
                            str(dx.threshold),
                            str(dx.current_count),
                            "Yes" if dx.achieved else "No",
                        ),
                        text=dx.name,
                    )
            # PFX Awards
            for pfx in result.pfx_awards:
                if pfx.current_score > 0 or pfx.achieved:
                    level_text = f"Px{pfx.level}"
                    band_text = pfx.band if pfx.band else "Overall"
                    score_text = f"{pfx.current_score:,}/{pfx.threshold:,}"
                    prefixes_text = str(pfx.unique_prefixes)
                    achieved_text = "Yes" if pfx.achieved else "No"
                    self.pfx_tree.insert(
                        "",
                        tk.END,
                        values=(
                            level_text,
                            band_text,
                            score_text,
                            prefixes_text,
                            achieved_text,
                        ),
                        text=pfx.name,
                    )
            # Triple Key
            for tk_award in result.triple_key_awards:
                perc = getattr(tk_award, "percentage", 0.0)
                self.triple_key_tree.insert(
                    "",
                    tk.END,
                    values=(
                        tk_award.name,
                        tk_award.current_count,
                        tk_award.threshold,
                        f"{perc:.1f}%",
                        "Yes" if tk_award.achieved else "No",
                    ),
                    text=tk_award.name,
                )
            # Rag Chew
            for rc in result.rag_chew_awards:
                if rc.current_minutes > 0 or rc.achieved:
                    level_text = f"RC{rc.level}"
                    band_text = rc.band if rc.band else "Overall"
                    minutes_text = f"{rc.current_minutes}/{rc.threshold}"
                    qsos_text = str(rc.qso_count)
                    self.rag_chew_tree.insert(
                        "",
                        tk.END,
                        values=(
                            level_text,
                            band_text,
                            minutes_text,
                            qsos_text,
                            "Yes" if rc.achieved else "No",
                        ),
                        text=rc.name,
                    )
            # WAC
            for wac in result.wac_awards:
                if wac.current_continents > 0 or wac.achieved:
                    continents_text = (
                        "/".join(wac.continents_worked) if wac.continents_worked else "None"
                    )
                    worked_text = f"{wac.current_continents}/6"
                    self.wac_tree.insert(
                        "",
                        tk.END,
                        values=(
                            wac.award_type,
                            wac.band if wac.band else "Overall",
                            continents_text,
                            worked_text,
                            "Yes" if wac.achieved else "No",
                        ),
                        text=wac.name,
                    )
            self.unique_var.set(
                f"Unique Members Worked: {result.unique_members_worked} | "
                f"QSOs matched/total: {result.matched_qsos}/{result.total_qsos} | "
                f"Unmatched calls: {len(result.unmatched_calls)}"
            )
            self.status_var.set("Computation complete.")
            # Persist summary context
            if self.adif_paths:
                _save_prefs(
                    {
                        "awards_adif_paths": [str(p) for p in self.adif_paths],
                        "last_unique_members": result.unique_members_worked,
                    }
                )
        elif kind == "error":
            msg = str(item[1])
            self.status_var.set(msg)
            messagebox.showerror("Error", msg)
        else:
            self.status_var.set(f"Unknown queue item: {kind}")


class CombinedApp(ttk.Frame):
    """Top-level combined application with tabs for Logger and Awards."""

    def __init__(self, master: tk.Tk):  # noqa: D401
        super().__init__(master)
        self.pack(fill=tk.BOTH, expand=True)

        master.title(APP_TITLE)
        master.geometry("1300x800")
        master.minsize(1100, 700)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)

        # Logger tab
        logger_container = ttk.Frame(nb)
        nb.add(logger_container, text="Logger")
        self.logger_form = QSOForm(logger_container)

        # Awards tab
        awards_container = ttk.Frame(nb)
        nb.add(awards_container, text="Awards")
        self.awards_panel = AwardsPanel(awards_container)

        # Provide logger form to awards panel for ADIF reuse
        self.awards_panel.set_logger_form(self.logger_form)

        # Attach trace for logger ADIF persistence
        def _logger_adif_changed(*_):  # noqa: D401
            path = self.logger_form.adif_var.get().strip()
            if path:
                _save_prefs({"logger_adif_path": path})

        self.logger_form.adif_var.trace_add("write", _logger_adif_changed)

        # Restore previous session preferences
        self._restore_previous_session()

        # Simple status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w", relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _restore_previous_session(self) -> None:
        prefs = _load_prefs()
        # Restore logger ADIF
        adif_path = prefs.get("logger_adif_path")
        if adif_path and Path(adif_path).exists():
            self.logger_form.adif_var.set(adif_path)
        # Restore awards ADIF list
        awards_paths = prefs.get("awards_adif_paths") or []
        restored: list[Path] = []
        for p in awards_paths:
            pp = Path(p)
            if pp.exists():
                restored.append(pp)
        if restored:
            self.awards_panel.clear_adif()
            for rp in restored:
                self.awards_panel.adif_paths.append(rp)
                self.awards_panel.adif_list.insert(tk.END, str(rp))
            self.awards_panel.status_var.set(
                f"Restored {len(restored)} awards ADIF file(s) from previous session"
            )
        # Restore roster mode
        roster_mode = prefs.get("roster_mode")
        if roster_mode == "csv":
            csv_path = prefs.get("roster_csv_path")
            if csv_path and self.awards_panel.load_roster_csv_from_path(Path(csv_path)):
                pass
        elif roster_mode == "live":
            # Defer a little so UI shows quickly then fetch
            self.after(750, self._fetch_live_roster)

    def _fetch_live_roster(self):  # noqa: D401
        self.awards_panel.load_roster_live()
        _save_prefs({"roster_mode": "live"})


def launch():  # Convenience external entry
    root = tk.Tk()
    app = CombinedApp(root)
    root.protocol("WM_DELETE_WINDOW", app.logger_form.close)  # ensure backup logic
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    launch()
