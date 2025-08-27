#!/usr/bin/env python
"""Tkinter GUI for SKCC Awards checker.

Features:
- Select one or more ADIF files
- Optionally load a roster CSV (number,call) for offline work
- Fetch live roster from SKCC site
- Compute awards + band/mode endorsements
- Display results in treeviews

Note: Network fetch is run in a background thread to avoid freezing the UI.
"""
from __future__ import annotations
import threading
import queue
import asyncio
import sys
import csv
from pathlib import Path
from typing import List, Optional, Iterable, Tuple
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Allow running from repo root (scripts/gui.py) to import backend logic
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

from services.skcc import (  # type: ignore  # noqa: E402
    parse_adif_files,
    fetch_member_roster,
    calculate_awards,
    Member,
)

APP_TITLE = "SKCC Awards GUI"

class AwardsGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x600")

        self.adif_paths: List[Path] = []
        self.members: List[Member] = []
        self.roster_loaded = False

        self.roster_url_var = tk.StringVar(value="")
        # Options vars
        self.include_unknown_var = tk.BooleanVar(value=False)
        self.enforce_key_var = tk.BooleanVar(value=False)
        self.missing_key_valid_var = tk.BooleanVar(value=True)
        self.enforce_suffix_var = tk.BooleanVar(value=True)  # Default to True for proper SKCC rules
        self.historical_status_var = tk.BooleanVar(value=True)  # Default to True for QSO-time status

        self._build_widgets()

        # Thread communication
        self.task_queue: queue.Queue = queue.Queue()
        self.root.after(150, self._poll_queue)

    # UI Construction
    def _build_widgets(self) -> None:
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Select ADIF files or load roster.")

        ttk.Button(top_frame, text="Add ADIF", command=self.select_adif).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Clear ADIF", command=self.clear_adif).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Load Roster (Live)", command=self.load_roster_live).pack(side=tk.LEFT, padx=8)
        ttk.Button(top_frame, text="Load Roster CSV", command=self.load_roster_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Compute", command=self.compute).pack(side=tk.LEFT, padx=16)
        ttk.Button(top_frame, text="Quit", command=self.root.destroy).pack(side=tk.RIGHT, padx=2)

        # Options frame
        opt_frame = ttk.Frame(self.root, padding=(8,0))
        opt_frame.pack(fill=tk.X)
        ttk.Checkbutton(opt_frame, text="Include unknown SKCC IDs", variable=self.include_unknown_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(opt_frame, text="Enforce key type", variable=self.enforce_key_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(opt_frame, text="Missing key OK", variable=self.missing_key_valid_var).pack(side=tk.LEFT, padx=4)
        
        # Second row of options
        opt_frame2 = ttk.Frame(self.root, padding=(8,0))
        opt_frame2.pack(fill=tk.X)
        ttk.Checkbutton(opt_frame2, text="Enforce SKCC suffix rules", variable=self.enforce_suffix_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(opt_frame2, text="Use historical status (award status at QSO time)", variable=self.historical_status_var).pack(side=tk.LEFT, padx=4)

        # Roster URL entry (optional)
        url_frame = ttk.Frame(self.root, padding=(8,0))
        url_frame.pack(fill=tk.X)
        ttk.Label(url_frame, text="Roster URL (optional):").pack(side=tk.LEFT)
        url_entry = ttk.Entry(url_frame, textvariable=self.roster_url_var, width=80)
        url_entry.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        ttk.Button(url_frame, text="Clear", command=lambda: self.roster_url_var.set("")).pack(side=tk.LEFT)

        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill=tk.X, padx=8, pady=(0, 4))

        # ADIF list
        adif_frame = ttk.LabelFrame(self.root, text="ADIF Files", padding=4)
        adif_frame.pack(fill=tk.X, padx=8, pady=4)
        self.adif_list = tk.Listbox(adif_frame, height=4)
        self.adif_list.pack(fill=tk.X)

        # Results notebook
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Awards tab
        awards_tab = ttk.Frame(notebook)
        notebook.add(awards_tab, text="Awards")

        self.awards_tree = ttk.Treeview(awards_tab, columns=("required", "current", "achieved"), show="headings")
        for col, txt, w in [("required", "Required", 80), ("current", "Current", 80), ("achieved", "Achieved", 80)]:
            self.awards_tree.heading(col, text=txt)
            self.awards_tree.column(col, width=w, anchor=tk.CENTER)
        self.awards_tree.pack(fill=tk.BOTH, expand=True)

        # Endorsements tab
        end_tab = ttk.Frame(notebook)
        notebook.add(end_tab, text="Endorsements")
        self.endorse_tree = ttk.Treeview(end_tab, columns=("category", "value", "current", "required"), show="headings")
        for col, txt, w in [
            ("category", "Category", 80),
            ("value", "Value", 100),
            ("current", "Current", 80),
            ("required", "Required", 80),
        ]:
            self.endorse_tree.heading(col, text=txt)
            self.endorse_tree.column(col, width=w, anchor=tk.CENTER)
        self.endorse_tree.pack(fill=tk.BOTH, expand=True)

        # Canadian Maple Awards tab
        maple_tab = ttk.Frame(notebook)
        notebook.add(maple_tab, text="Canadian Maple")
        self.maple_tree = ttk.Treeview(maple_tab, columns=("level", "band", "provinces", "achieved"), show="headings")
        for col, txt, w in [
            ("level", "Level", 80),
            ("band", "Band", 80),
            ("provinces", "Provinces", 100),
            ("achieved", "Achieved", 80),
        ]:
            self.maple_tree.heading(col, text=txt)
            self.maple_tree.column(col, width=w, anchor=tk.CENTER)
        self.maple_tree.pack(fill=tk.BOTH, expand=True)

        # DX Awards tab
        dx_tab = ttk.Frame(notebook)
        notebook.add(dx_tab, text="DX Awards")
        self.dx_tree = ttk.Treeview(dx_tab, columns=("type", "threshold", "current", "achieved"), show="headings")
        for col, txt, w in [
            ("type", "Type", 80),
            ("threshold", "Threshold", 80),
            ("current", "Current", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.dx_tree.heading(col, text=txt)
            self.dx_tree.column(col, width=w, anchor=tk.CENTER)
        self.dx_tree.pack(fill=tk.BOTH, expand=True)

        # PFX Awards tab
        pfx_tab = ttk.Frame(notebook)
        notebook.add(pfx_tab, text="PFX Awards")
        self.pfx_tree = ttk.Treeview(pfx_tab, columns=("level", "band", "score", "prefixes", "achieved"), show="headings")
        for col, txt, w in [
            ("level", "Level", 60),
            ("band", "Band", 60),
            ("score", "Score", 100),
            ("prefixes", "Prefixes", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.pfx_tree.heading(col, text=txt)
            self.pfx_tree.column(col, width=w, anchor=tk.CENTER)
        self.pfx_tree.pack(fill=tk.BOTH, expand=True)

        # Triple Key Awards tab
        triple_key_tab = ttk.Frame(notebook)
        notebook.add(triple_key_tab, text="Triple Key")
        self.triple_key_tree = ttk.Treeview(triple_key_tab, columns=("key_type", "current", "threshold", "percentage", "achieved"), show="headings")
        for col, txt, w in [
            ("key_type", "Key Type", 120),
            ("current", "Current", 80),
            ("threshold", "Threshold", 80),
            ("percentage", "Progress", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.triple_key_tree.heading(col, text=txt)
            self.triple_key_tree.column(col, width=w, anchor=tk.CENTER)
        self.triple_key_tree.pack(fill=tk.BOTH, expand=True)

        # Rag Chew Awards tab
        rag_chew_tab = ttk.Frame(notebook)
        notebook.add(rag_chew_tab, text="Rag Chew")
        self.rag_chew_tree = ttk.Treeview(rag_chew_tab, columns=("level", "band", "minutes", "qsos", "achieved"), show="headings")
        for col, txt, w in [
            ("level", "Level", 80),
            ("band", "Band", 60),
            ("minutes", "Minutes", 100),
            ("qsos", "QSOs", 60),
            ("achieved", "Achieved", 80),
        ]:
            self.rag_chew_tree.heading(col, text=txt)
            self.rag_chew_tree.column(col, width=w, anchor=tk.CENTER)
        self.rag_chew_tree.pack(fill=tk.BOTH, expand=True)

        # Unique count
        bottom = ttk.Frame(self.root, padding=4)
        bottom.pack(fill=tk.X)
        self.unique_var = tk.StringVar(value="Unique Members Worked: -")
        ttk.Label(bottom, textvariable=self.unique_var, anchor="w").pack(side=tk.LEFT)

    # Actions
    def select_adif(self) -> None:
        paths = filedialog.askopenfilenames(title="Select ADIF files", filetypes=[("ADIF", "*.adi *.adif"), ("All", "*.*")])
        if not paths:
            return
        for p in paths:
            path_obj = Path(p)
            if path_obj not in self.adif_paths:
                self.adif_paths.append(path_obj)
                self.adif_list.insert(tk.END, str(path_obj))
        self.status_var.set(f"Loaded {len(self.adif_paths)} ADIF file(s).")

    def clear_adif(self) -> None:
        self.adif_paths.clear()
        self.adif_list.delete(0, tk.END)
        self.status_var.set("ADIF list cleared.")

    def load_roster_csv(self) -> None:
        path = filedialog.askopenfilename(title="Select Roster CSV", filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return
        try:
            self.members = self._read_members_csv(Path(path))
            self.roster_loaded = True
            self.status_var.set(f"Loaded {len(self.members)} members from CSV.")
        except Exception as e:  # pragma: no cover
            messagebox.showerror("Roster CSV Error", str(e))

    def load_roster_live(self) -> None:
        self.status_var.set("Fetching live roster...")
        threading.Thread(target=self._fetch_roster_thread, daemon=True).start()

    def _fetch_roster_thread(self) -> None:
        try:
            custom_url = self.roster_url_var.get().strip() or None
            members = asyncio.run(fetch_member_roster(url=custom_url))
            self.task_queue.put(("roster", members))
        except Exception as e:  # pragma: no cover
            self.task_queue.put(("error", f"Roster fetch failed: {e}"))

    def compute(self) -> None:
        if not self.adif_paths:
            messagebox.showwarning("No ADIF", "Please select at least one ADIF file.")
            return
        if not self.members and not self.roster_loaded:
            # Try live fetch automatically
            self.status_var.set("Auto-fetching roster (no local roster loaded)...")
            threading.Thread(target=self._compute_with_live_roster, daemon=True).start()
        else:
            threading.Thread(target=self._compute_thread, daemon=True).start()

    def _compute_with_live_roster(self) -> None:
        try:
            custom_url = self.roster_url_var.get().strip() or None
            members = asyncio.run(fetch_member_roster(url=custom_url))
            self.members = members
            self.roster_loaded = True
        except Exception as e:  # pragma: no cover
            self.task_queue.put(("error", f"Live roster fetch failed: {e}"))
            return
        self._compute_thread()

    def _compute_thread(self) -> None:
        try:
            adif_contents = [p.read_text(encoding="utf-8", errors="ignore") for p in self.adif_paths]
            qsos = parse_adif_files(adif_contents)
            result = calculate_awards(
                qsos,
                self.members,
                cw_only=True,
                include_unknown_ids=self.include_unknown_var.get(),
                enforce_key_type=self.enforce_key_var.get(),
                treat_missing_key_as_valid=self.missing_key_valid_var.get(),
                enforce_suffix_rules=self.enforce_suffix_var.get(),
            )
            self.task_queue.put(("result", result))
        except Exception as e:  # pragma: no cover
            self.task_queue.put(("error", f"Computation failed: {e}"))

    # Helpers
    def _read_members_csv(self, path: Path) -> List[Member]:
        out: List[Member] = []
        with path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                try:
                    number = int(row[0].strip())
                    call = row[1].strip().upper()
                except (ValueError, IndexError):
                    continue
                out.append(Member(call=call, number=number))
        return out

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.task_queue.get_nowait()
                self._handle_task_item(item)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _handle_task_item(self, item) -> None:
        kind = item[0]
        if kind == "roster":
            self.members = item[1]
            self.roster_loaded = True
            self.status_var.set(f"Live roster loaded: {len(self.members)} members.")
        elif kind == "result":
            result = item[1]
            # Update awards tree
            for tree in (self.awards_tree, self.endorse_tree, self.maple_tree, self.dx_tree, self.pfx_tree, self.triple_key_tree, self.rag_chew_tree):
                for iid in tree.get_children():
                    tree.delete(iid)
            for a in result.awards:
                self.awards_tree.insert("", tk.END, values=(a.required, a.current, "Yes" if a.achieved else "No"), text=a.name, tags=("ach" if a.achieved else ""))
            # Show name in separate column using heading? Instead create first column implicit #0
            self.awards_tree.configure(show="tree headings")
            for i, iid in enumerate(self.awards_tree.get_children()):
                # Set item text to award name
                award_obj = result.awards[i]
                self.awards_tree.item(iid, text=award_obj.name)
            for e in result.endorsements:
                self.endorse_tree.insert("", tk.END, values=(e.category, e.value, e.current, e.required), text=e.award)
            
            # Display Canadian Maple Awards
            for maple in result.canadian_maple_awards:
                band_text = maple.band if maple.band else "All"
                province_text = f"{maple.current_provinces}/{maple.required_provinces}"
                achieved_text = "Yes" if maple.achieved else "No"
                qrp_text = " (QRP)" if maple.qrp_required else ""
                level_text = f"{maple.level}{qrp_text}"
                
                self.maple_tree.insert("", tk.END, 
                                     values=(level_text, band_text, province_text, achieved_text),
                                     text=maple.name,
                                     tags=("ach" if maple.achieved else ""))
            
            # Display DX Awards
            for dx in result.dx_awards:
                if dx.current_count > 0 or dx.achieved:  # Only show if there's progress
                    type_text = dx.award_type
                    if dx.qrp_qualified:
                        type_text += " QRP"
                    threshold_text = str(dx.threshold)
                    current_text = str(dx.current_count)
                    achieved_text = "Yes" if dx.achieved else "No"
                    
                    self.dx_tree.insert("", tk.END,
                                      values=(type_text, threshold_text, current_text, achieved_text),
                                      text=dx.name,
                                      tags=("ach" if dx.achieved else ""))
            
            # Display PFX Awards
            for pfx in result.pfx_awards:
                if pfx.current_score > 0 or pfx.achieved:  # Only show if there's progress
                    level_text = f"Px{pfx.level}"
                    band_text = pfx.band if pfx.band else "Overall"
                    score_text = f"{pfx.current_score:,}/{pfx.threshold:,}"
                    prefixes_text = str(pfx.unique_prefixes)
                    achieved_text = "Yes" if pfx.achieved else "No"
                    
                    self.pfx_tree.insert("", tk.END,
                                       values=(level_text, band_text, score_text, prefixes_text, achieved_text),
                                       text=pfx.name,
                                       tags=("ach" if pfx.achieved else ""))
            
            # Display Triple Key Awards
            for tk_award in result.triple_key_awards:
                if tk_award.current_count > 0 or tk_award.achieved:  # Only show if there's progress
                    key_type_text = tk_award.name
                    current_text = str(tk_award.current_count)
                    threshold_text = str(tk_award.threshold)
                    percentage_text = f"{tk_award.percentage:.1f}%"
                    achieved_text = "Yes" if tk_award.achieved else "No"
                    
                    self.triple_key_tree.insert("", tk.END,
                                               values=(key_type_text, current_text, threshold_text, percentage_text, achieved_text),
                                               text=tk_award.name,
                                               tags=("ach" if tk_award.achieved else ""))
            
            # Display Rag Chew Awards
            for rc_award in result.rag_chew_awards:
                if rc_award.current_minutes > 0 or rc_award.achieved:  # Only show if there's progress
                    level_text = f"RC{rc_award.level}"
                    band_text = rc_award.band if rc_award.band else "Overall"
                    minutes_text = f"{rc_award.current_minutes}/{rc_award.threshold}"
                    qsos_text = str(rc_award.qso_count)
                    achieved_text = "Yes" if rc_award.achieved else "No"
                    
                    self.rag_chew_tree.insert("", tk.END,
                                            values=(level_text, band_text, minutes_text, qsos_text, achieved_text),
                                            text=rc_award.name,
                                            tags=("ach" if rc_award.achieved else ""))
            
            self.unique_var.set(
                f"Unique Members Worked: {result.unique_members_worked} | QSOs matched/total: {result.matched_qsos}/{result.total_qsos} | Unmatched calls: {len(result.unmatched_calls)}"
            )
            self.status_var.set("Computation complete. (CW-only QSOs considered)")
        elif kind == "error":
            self.status_var.set(item[1])
            messagebox.showerror("Error", item[1])


def main() -> None:
    root = tk.Tk()
    # Attach instance to root to avoid lint warning and ensure longevity
    root.app = AwardsGUI(root)  # type: ignore[attr-defined]
    root.mainloop()

if __name__ == "__main__":  # pragma: no cover
    main()
