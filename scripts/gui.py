#!/usr/bin/env python
"""Tkinter GUI for SKCC Awards checker.

Features:
- Select one or more ADIF files
- Optionally load a roster CSV (number,call) for offline work
- Fetch live roster from SKCC site
- Compute awards + band endorsements
- Display results in treeviews

Note: Network fetch is run in a background thread to avoid freezing the UI.
"""
from __future__ import annotations
import threading
import queue
import asyncio
import sys
import csv
import re
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
    parse_adif,
    fetch_member_roster,
    calculate_awards,
    Member,
)

APP_TITLE = "SKCC Awards GUI"

# Custom exceptions for better error handling
class SKCCAwardsError(Exception):
    """Base exception for SKCC Awards application."""
    pass

class FileValidationError(SKCCAwardsError):
    """Raised when file validation fails."""
    pass

class URLValidationError(SKCCAwardsError):
    """Raised when URL validation fails."""
    pass

class RosterFetchError(SKCCAwardsError):
    """Raised when roster fetching fails."""
    pass

class ADIFParsingError(SKCCAwardsError):
    """Raised when ADIF parsing fails."""
    pass

class CSVImportError(SKCCAwardsError):
    """Raised when CSV import fails."""
    pass

class AwardsCalculationError(SKCCAwardsError):
    """Raised when awards calculation fails."""
    pass

# Regex patterns for validation
URL_PATTERN = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
ADIF_EXTENSION_PATTERN = re.compile(r'\.(adi|adif)$', re.IGNORECASE)
CALLSIGN_PATTERN = re.compile(r'^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]$')
MEMBER_NUMBER_PATTERN = re.compile(r'^\d+$')

# Test function for regex patterns (can be removed in production)
def _test_regex_patterns() -> None:
    """Test regex patterns with sample data."""
    # Test URLs
    valid_urls = ["https://www.skccgroup.com/roster", "http://example.com/data.csv"]
    invalid_urls = ["ftp://invalid.com", "not a url", ""]

    # Test ADIF extensions
    valid_adif = ["log.adi", "contest.adif", "TEST.ADI"]
    invalid_adif = ["log.txt", "data.csv", "file.log"]

    # Test callsigns
    valid_calls = ["W1ABC", "K0DEF", "VE3GHI", "G0JKL"]
    invalid_calls = ["123ABC", "TOOLONG", "AB", ""]

    # Test member numbers
    valid_numbers = ["12345", "1", "999999"]
    invalid_numbers = ["abc", "12.34", "", "12a34"]

    print("Testing regex patterns...")
    # Add actual test logic here if needed for debugging

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
            ("key_type", "Key Type", 150),
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

        # WAC Awards tab
        wac_tab = ttk.Frame(notebook)
        notebook.add(wac_tab, text="WAC Awards")
        self.wac_tree = ttk.Treeview(wac_tab, columns=("award_type", "band", "continents", "worked", "achieved"), show="headings")
        for col, txt, w in [
            ("award_type", "Award Type", 150),
            ("band", "Band", 60),
            ("continents", "Continents", 200),
            ("worked", "Worked", 80),
            ("achieved", "Achieved", 80),
        ]:
            self.wac_tree.heading(col, text=txt)
            self.wac_tree.column(col, width=w, anchor=tk.CENTER)
        self.wac_tree.pack(fill=tk.BOTH, expand=True)

        # Unique count
        bottom = ttk.Frame(self.root, padding=4)
        bottom.pack(fill=tk.X)
        self.unique_var = tk.StringVar(value="Unique Members Worked: -")
        ttk.Label(bottom, textvariable=self.unique_var, anchor="w").pack(side=tk.LEFT)

    # Actions
    def select_adif(self) -> None:
        try:
            paths = filedialog.askopenfilenames(title="Select ADIF files", filetypes=[("ADIF", "*.adi *.adif"), ("All", "*.*")])
            if not paths:
                return
            
            invalid_files = []
            valid_files_added = 0
            
            for p in paths:
                try:
                    path_obj = Path(p)
                    
                    # Check if file exists and is readable
                    if not path_obj.exists():
                        raise FileValidationError(f"File does not exist: {path_obj}")
                    
                    if not path_obj.is_file():
                        raise FileValidationError(f"Path is not a file: {path_obj}")
                    
                    # Check file size (warn if very large)
                    file_size = path_obj.stat().st_size
                    if file_size > 50 * 1024 * 1024:  # 50MB
                        result = messagebox.askyesno(
                            "Large File Warning", 
                            f"File {path_obj.name} is {file_size / (1024*1024):.1f}MB. Continue?"
                        )
                        if not result:
                            continue
                    
                    # Use regex to validate ADIF file extensions
                    if not ADIF_EXTENSION_PATTERN.search(path_obj.name):
                        invalid_files.append(f"{path_obj.name} (invalid extension)")
                        continue
                    
                    # Try to read a small portion to verify it's text
                    try:
                        with path_obj.open('r', encoding='utf-8', errors='ignore') as f:
                            sample = f.read(1024)
                            if not sample.strip():
                                raise FileValidationError(f"File appears to be empty: {path_obj.name}")
                    except (UnicodeDecodeError, PermissionError) as e:
                        raise FileValidationError(f"Cannot read file {path_obj.name}: {e}")
                    
                    if path_obj not in self.adif_paths:
                        self.adif_paths.append(path_obj)
                        self.adif_list.insert(tk.END, str(path_obj))
                        valid_files_added += 1
                    
                except FileValidationError as e:
                    invalid_files.append(str(e))
                except Exception as e:
                    invalid_files.append(f"{path_obj.name if 'path_obj' in locals() else p} (error: {e})")
            
            if invalid_files:
                messagebox.showwarning("File Validation Issues", f"Issues encountered:\n" + "\n".join(invalid_files))
            
            if valid_files_added > 0:
                self.status_var.set(f"Added {valid_files_added} ADIF file(s). Total: {len(self.adif_paths)}")
            else:
                self.status_var.set("No valid ADIF files were added.")
                
        except Exception as e:
            error_msg = f"Unexpected error during file selection: {e}"
            self.status_var.set(error_msg)
            messagebox.showerror("File Selection Error", error_msg)

    def clear_adif(self) -> None:
        self.adif_paths.clear()
        self.adif_list.delete(0, tk.END)
        self.status_var.set("ADIF list cleared.")

    def load_roster_csv(self) -> None:
        try:
            path = filedialog.askopenfilename(title="Select Roster CSV", filetypes=[("CSV", "*.csv"), ("All", "*.*")])
            if not path:
                return
                
            path_obj = Path(path)
            
            # Validate file before processing
            if not path_obj.exists():
                raise CSVImportError(f"File does not exist: {path_obj}")
            
            if not path_obj.is_file():
                raise CSVImportError(f"Path is not a file: {path_obj}")
            
            # Check file size
            file_size = path_obj.stat().st_size
            if file_size == 0:
                raise CSVImportError("CSV file is empty")
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                result = messagebox.askyesno(
                    "Large CSV Warning", 
                    f"CSV file is {file_size / (1024*1024):.1f}MB. This may take a while. Continue?"
                )
                if not result:
                    return
            
            self.members = self._read_members_csv(path_obj)
            self.roster_loaded = True
            self.status_var.set(f"Loaded {len(self.members)} members from CSV.")
            
        except CSVImportError as e:
            messagebox.showerror("CSV Import Error", str(e))
            self.status_var.set(f"CSV import failed: {e}")
        except Exception as e:
            error_msg = f"Unexpected error during CSV import: {e}"
            messagebox.showerror("CSV Import Error", error_msg)
            self.status_var.set(error_msg)

    def load_roster_live(self) -> None:
        try:
            # Validate URL if provided
            custom_url = self.roster_url_var.get().strip()
            if custom_url:
                if not URL_PATTERN.match(custom_url):
                    raise URLValidationError("Please enter a valid HTTP/HTTPS URL or leave blank for default.")
                
                # Additional URL safety checks
                forbidden_patterns = ['localhost', '127.0.0.1', '0.0.0.0', 'file://', 'ftp://']
                if any(pattern in custom_url.lower() for pattern in forbidden_patterns):
                    raise URLValidationError("URL contains forbidden patterns for security reasons.")
            
            self.status_var.set("Fetching live roster...")
            threading.Thread(target=self._fetch_roster_thread, daemon=True).start()
            
        except URLValidationError as e:
            messagebox.showerror("Invalid URL", str(e))
            self.status_var.set(f"URL validation failed: {e}")
        except Exception as e:
            error_msg = f"Unexpected error starting roster fetch: {e}"
            messagebox.showerror("Roster Fetch Error", error_msg)
            self.status_var.set(error_msg)

    def _fetch_roster_thread(self) -> None:
        try:
            custom_url = self.roster_url_var.get().strip() or None
            members = asyncio.run(fetch_member_roster(url=custom_url))
            
            if not members:
                raise RosterFetchError("No members found in roster")
            
            if len(members) < 100:  # Sanity check - SKCC should have more than 100 members
                raise RosterFetchError(f"Roster seems incomplete: only {len(members)} members found")
            
            self.task_queue.put(("roster", members))
            
        except asyncio.TimeoutError:
            self.task_queue.put(("error", "Roster fetch timed out. Please check your internet connection."))
        except RosterFetchError as e:
            self.task_queue.put(("error", f"Roster fetch failed: {e}"))
        except Exception as e:
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
            if not self.adif_paths:
                raise AwardsCalculationError("No ADIF files selected")
            
            if not self.members:
                raise AwardsCalculationError("No roster loaded")
            
            # Read and validate ADIF files
            adif_contents = []
            for path in self.adif_paths:
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    if not content.strip():
                        raise ADIFParsingError(f"ADIF file is empty: {path.name}")
                    
                    # Basic ADIF format check
                    if '<EOR>' not in content and '<eor>' not in content:
                        raise ADIFParsingError(f"ADIF file appears to be missing EOR markers: {path.name}")
                    
                    adif_contents.append(content)
                    
                except (OSError, PermissionError) as e:
                    raise ADIFParsingError(f"Cannot read ADIF file {path.name}: {e}")
            
            # Parse ADIF files
            all_qsos = []
            for i, content in enumerate(adif_contents):
                try:
                    qsos = parse_adif(content)
                    if not qsos:
                        print(f"Warning: No QSOs found in file {self.adif_paths[i].name}")
                    all_qsos.extend(qsos)
                except Exception as e:
                    raise ADIFParsingError(f"Failed to parse ADIF file {self.adif_paths[i].name}: {e}")
            
            if not all_qsos:
                raise AwardsCalculationError("No QSOs found in any ADIF file")
            
            # Calculate awards
            result = calculate_awards(
                all_qsos,
                self.members,
                enforce_key_type=self.enforce_key_var.get(),
                treat_missing_key_as_valid=self.missing_key_valid_var.get(),
                enforce_suffix_rules=self.enforce_suffix_var.get(),
            )
            
            if result is None:
                raise AwardsCalculationError("Awards calculation returned no results")
            
            self.task_queue.put(("result", result))
            
        except (ADIFParsingError, AwardsCalculationError) as e:
            self.task_queue.put(("error", str(e)))
        except Exception as e:
            self.task_queue.put(("error", f"Computation failed: {e}"))

    def _read_members_csv(self, path: Path) -> List[Member]:
        try:
            out: List[Member] = []
            invalid_rows = 0
            total_rows = 0
            
            with path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
                # Try to detect CSV dialect
                try:
                    sample = f.read(2048)
                    f.seek(0)
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
                    reader = csv.reader(f, dialect)
                except csv.Error:
                    # Fall back to default comma delimiter
                    f.seek(0)
                    reader = csv.reader(f)
                
                for row_num, row in enumerate(reader, 1):
                    total_rows += 1
                    
                    if not row or len(row) < 2:  # Ensure at least 2 columns
                        invalid_rows += 1
                        continue
                        
                    try:
                        # Use regex to validate member number
                        number_str = row[0].strip()
                        if not number_str or not MEMBER_NUMBER_PATTERN.match(number_str):
                            invalid_rows += 1
                            continue
                        
                        number = int(number_str)
                        if number <= 0 or number > 999999:  # Reasonable bounds
                            invalid_rows += 1
                            continue
                        
                        call = row[1].strip().upper()
                        
                        # Validate callsign is not empty
                        if not call or len(call) < 3 or len(call) > 10:
                            invalid_rows += 1
                            continue
                        
                        # Optional: validate callsign format (warn but don't reject)
                        if not CALLSIGN_PATTERN.match(call):
                            print(f"Warning: Unusual callsign format '{call}' in row {row_num}")
                        
                        # Check for duplicates
                        if any(m.call == call or m.number == number for m in out):
                            print(f"Warning: Duplicate member {call}/{number} in row {row_num}")
                            continue
                        
                        out.append(Member(call=call, number=number))
                        
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Error processing row {row_num}: {e}")
                        invalid_rows += 1
                        continue
            
            if total_rows == 0:
                raise CSVImportError("CSV file contains no data rows")
            
            if len(out) == 0:
                raise CSVImportError("No valid member records found in CSV file")
            
            if invalid_rows > 0:
                messagebox.showwarning("CSV Import", 
                    f"Processed {total_rows} rows, skipped {invalid_rows} invalid rows. "
                    f"Successfully imported {len(out)} members.")
            
            return out
            
        except (OSError, PermissionError) as e:
            raise CSVImportError(f"Cannot read CSV file: {e}")
        except csv.Error as e:
            raise CSVImportError(f"CSV parsing error: {e}")
        except Exception as e:
            raise CSVImportError(f"Unexpected error reading CSV: {e}")

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.task_queue.get_nowait()
                self._handle_task_item(item)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _handle_task_item(self, item) -> None:
        try:
            kind = item[0]
            if kind == "roster":
                members = item[1]
                if not isinstance(members, list):
                    raise RosterFetchError("Invalid roster data received")
                
                self.members = members
                self.roster_loaded = True
                self.status_var.set(f"Live roster loaded: {len(self.members)} members.")
                
            elif kind == "result":
                result = item[1]
                if result is None:
                    raise AwardsCalculationError("No results received from calculation")
                
                # Update awards tree
                for tree in (self.awards_tree, self.endorse_tree, self.maple_tree, 
                           self.dx_tree, self.pfx_tree, self.triple_key_tree, 
                           self.rag_chew_tree, self.wac_tree):
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
                    # Always show all Triple Key awards, even with 0 progress for better visibility
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
                
                # Display WAC Awards
                for wac_award in result.wac_awards:
                    if wac_award.current_continents > 0 or wac_award.achieved:  # Only show if there's progress
                        award_type_text = wac_award.award_type
                        band_text = wac_award.band if wac_award.band else "Overall"
                        continents_text = "/".join(wac_award.continents_worked) if wac_award.continents_worked else "None"
                        worked_text = f"{wac_award.current_continents}/6"
                        achieved_text = "Yes" if wac_award.achieved else "No"
                        
                        self.wac_tree.insert("", tk.END,
                                           values=(award_type_text, band_text, continents_text, worked_text, achieved_text),
                                           text=wac_award.name,
                                           tags=("ach" if wac_award.achieved else ""))
                
                self.unique_var.set(
                    f"Unique Members Worked: {result.unique_members_worked} | "
                    f"QSOs matched/total: {result.matched_qsos}/{result.total_qsos} | "
                    f"Unmatched calls: {len(result.unmatched_calls)}"
                )
                self.status_var.set("Computation complete. (SKCC - Morse code/CW operation)")
                
            elif kind == "error":
                error_msg = str(item[1])
                self.status_var.set(error_msg)
                messagebox.showerror("Error", error_msg)
            else:
                raise ValueError(f"Unknown task item type: {kind}")
                
        except Exception as e:
            error_msg = f"Error handling task result: {e}"
            self.status_var.set(error_msg)
            messagebox.showerror("Internal Error", error_msg)

def main() -> None:
    root = tk.Tk()
    # Attach instance to root to avoid lint warning and ensure longevity
    root.app = AwardsGUI(root)  # type: ignore[attr-defined]
    root.mainloop()

if __name__ == "__main__":  # pragma: no cover
    main()
