#!/usr/bin/env python3
"""Clean QSO Form with Country/State Support."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timezone
import sys
import threading
import json
import shutil
from pathlib import Path

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.key_type import KeyType, DISPLAY_LABELS, normalize
from models.qso import QSO
from adif_io.adif_writer import append_record
from utils.roster_manager import RosterManager
from utils.backup_manager import backup_manager

# Add backend services for country lookup
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

try:
    from services.skcc import get_dxcc_country
except ImportError:
    # Fallback if backend services not available
    def get_dxcc_country(call):
        return None

class QSOForm(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master, padding=12)
        self.pack(fill="both", expand=True)
        
        # QSO timing tracking
        self.qso_start_time = None  # Will be set when callsign is entered
        
        # Initialize roster manager
        self.roster_manager = RosterManager()
        
        # Initialize backup configuration
        self.backup_config_file = Path.home() / ".skcc_awards" / "backup_config.json"
        self.backup_config = self._load_backup_config()
        
        self._build_widgets()
        self._update_time_display()

    def _load_backup_config(self) -> dict:
        """Load backup configuration from file."""
        default_config = {
            "backup_enabled": True,
            "backup_folder": str(Path.home() / ".skcc_awards" / "backups"),
        }
        
        try:
            if self.backup_config_file.exists():
                with open(self.backup_config_file, 'r') as f:
                    config = json.load(f)
                    return {**default_config, **config}
        except Exception:
            pass
        
        return default_config

    def _build_widgets(self):
        r = 0
        
        # File selection
        ttk.Label(self, text="ADIF Log File").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        file_frame = ttk.Frame(self)
        file_frame.grid(row=r, column=1, sticky="ew", padx=6, pady=4)
        self.adif_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.adif_var, width=40).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(file_frame, text="Browse", command=self._browse_adif).pack(side=tk.LEFT)
        r += 1

        # Time display
        ttk.Label(self, text="QSO Time:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.time_display_var = tk.StringVar()
        ttk.Label(self, textvariable=self.time_display_var, foreground="green").grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Call with auto-complete
        ttk.Label(self, text="Call").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.call_var = tk.StringVar()
        self.call_entry = ttk.Entry(self, textvariable=self.call_var, width=20)
        self.call_entry.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.call_var.trace_add('write', self._on_callsign_change)
        
        # Auto-complete listbox (initially hidden)
        self.autocomplete_frame = ttk.Frame(self)
        self.autocomplete_listbox = tk.Listbox(self.autocomplete_frame, height=5, width=30)
        self.autocomplete_listbox.bind('<Double-Button-1>', self._select_autocomplete)
        r += 1

        # Freq & Band
        ttk.Label(self, text="Freq (MHz)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.freq_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.freq_var, width=10).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        ttk.Label(self, text="Band (e.g. 40M)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.band_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.band_var, width=10).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Reports
        ttk.Label(self, text="RST sent").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.rst_s_var = tk.StringVar(value="599")
        ttk.Entry(self, textvariable=self.rst_s_var, width=6).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        ttk.Label(self, text="RST rcvd").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.rst_r_var = tk.StringVar(value="599")
        ttk.Entry(self, textvariable=self.rst_r_var, width=6).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Power
        ttk.Label(self, text="Power (W)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.pwr_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.pwr_var, width=6).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # SKCC numbers
        ttk.Label(self, text="Their SKCC #").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.their_skcc_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.their_skcc_var, width=12).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Country (auto-filled from callsign)
        ttk.Label(self, text="Country").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.country_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.country_var, width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # State (manual entry for US stations)
        ttk.Label(self, text="State/Province").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.state_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.state_var, width=8).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Key used (REQUIRED for Triple Key)
        ttk.Label(self, text="Key used").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.key_var = tk.StringVar()
        options = [
            DISPLAY_LABELS[KeyType.STRAIGHT],
            DISPLAY_LABELS[KeyType.BUG],
            DISPLAY_LABELS[KeyType.SIDESWIPER],
        ]
        self.key_combo = ttk.Combobox(self, textvariable=self.key_var, values=options, state="readonly", width=20)
        self.key_combo.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.key_combo.current(0)
        r += 1

        # Buttons
        btn_row = ttk.Frame(self)
        btn_row.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(btn_row, text="Save QSO", command=self._save).grid(row=0, column=0, padx=6)
        ttk.Button(btn_row, text="Backup Config", command=self._configure_backup).grid(row=0, column=1, padx=6)
        ttk.Button(btn_row, text="Quit", command=self._quit).grid(row=0, column=2, padx=6)
        r += 1

        # Recent QSOs view
        ttk.Label(self, text="Recent QSOs:").grid(row=r, column=0, columnspan=3, sticky="w", padx=6, pady=(20, 5))
        r += 1
        
        # Create treeview for recent QSOs
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=r, column=0, columnspan=3, sticky="ew", padx=6, pady=5)
        
        # Configure treeview columns
        columns = ("Time", "Call", "Band", "SKCC", "Key")
        self.qso_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        
        # Configure column headings and widths
        self.qso_tree.heading("Time", text="Time (Local)")
        self.qso_tree.heading("Call", text="Call")
        self.qso_tree.heading("Band", text="Band")
        self.qso_tree.heading("SKCC", text="SKCC #")
        self.qso_tree.heading("Key", text="Key")
        
        self.qso_tree.column("Time", width=90, minwidth=80)
        self.qso_tree.column("Call", width=90, minwidth=80)
        self.qso_tree.column("Band", width=70, minwidth=60)
        self.qso_tree.column("SKCC", width=80, minwidth=60)
        self.qso_tree.column("Key", width=120, minwidth=100)
        
        # Add scrollbar for treeview
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.qso_tree.yview)
        self.qso_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        # Pack treeview and scrollbar
        self.qso_tree.pack(side=tk.LEFT, fill="both", expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill="y")
        
        # Configure grid weights for proper resizing
        self.columnconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)

    def _browse_adif(self):
        file_path = filedialog.askopenfilename(
            title="Select ADIF file",
            filetypes=[("ADIF files", "*.adif *.adi"), ("All files", "*.*")]
        )
        if file_path:
            self.adif_var.set(file_path)

    def _update_time_display(self):
        try:
            now = datetime.now()
            utc_now = now.astimezone(timezone.utc)
            display_time = f"{now.strftime('%H:%M:%S')} local ({utc_now.strftime('%H:%M:%S')} UTC)"
            self.time_display_var.set(display_time)
            self.after(1000, self._update_time_display)
        except Exception as e:
            print(f"Time display error: {e}")
            self.after(5000, self._update_time_display)

    def _on_callsign_change(self, *args):
        """Handle callsign field changes for auto-complete and country lookup."""
        callsign = self.call_var.get().upper().strip()
        
        # Lookup country from callsign
        if callsign:
            try:
                country = get_dxcc_country(callsign)
                if country:
                    self.country_var.set(country)
                else:
                    self.country_var.set("")
            except Exception as e:
                print(f"Country lookup error: {e}")
        
        if len(callsign) >= 2:  # Start suggesting after 2 characters
            try:
                # Search for matching callsigns
                matches = self.roster_manager.search_callsigns(callsign, limit=10)
                
                # Check for exact match and auto-fill SKCC number and state
                exact_match = None
                for match in matches:
                    if match['call'].upper() == callsign.upper():
                        exact_match = match
                        break
                
                if exact_match:
                    # Auto-fill SKCC number for exact match
                    if not self.their_skcc_var.get():
                        self.their_skcc_var.set(exact_match['number'])
                    
                    # Auto-fill state for exact match (only if currently empty)
                    if not self.state_var.get() and exact_match.get('state'):
                        self.state_var.set(exact_match['state'])
                
                # Also try direct member lookup for more complete information
                try:
                    member_info = self.roster_manager.lookup_member(callsign)
                    if member_info:
                        if not self.their_skcc_var.get():
                            self.their_skcc_var.set(member_info['number'])
                        if not self.state_var.get() and member_info.get('state'):
                            self.state_var.set(member_info['state'])
                except Exception as e:
                    print(f"Member lookup error: {e}")
                
                if matches:
                    # Show autocomplete listbox
                    self.autocomplete_listbox.delete(0, tk.END)
                    for match in matches:
                        display_text = f"{match['call']} - SKCC #{match['number']}"
                        self.autocomplete_listbox.insert(tk.END, display_text)
                    
                    # Position the autocomplete listbox below the callsign entry
                    self.autocomplete_frame.grid(row=self.call_entry.grid_info()['row'] + 1, 
                                               column=1, sticky="w", padx=6, pady=2)
                    self.autocomplete_listbox.pack()
                else:
                    self._hide_autocomplete()
            except Exception as e:
                print(f"Autocomplete error: {e}")
                self._hide_autocomplete()
        else:
            self._hide_autocomplete()
            # Clear SKCC number if callsign is too short
            if len(callsign) < 2:
                self.their_skcc_var.set("")

    def _hide_autocomplete(self):
        """Hide the autocomplete listbox."""
        self.autocomplete_frame.grid_remove()

    def _select_autocomplete(self, event=None):
        """Handle selection from autocomplete listbox."""
        try:
            selection = self.autocomplete_listbox.get(self.autocomplete_listbox.curselection())
            if selection:
                # Extract callsign from "CALL - SKCC #NUMBER" format
                call = selection.split(' - ')[0]
                self.call_var.set(call)
                self._hide_autocomplete()
        except Exception as e:
            print(f"Autocomplete selection error: {e}")

    def _save(self):
        try:
            if not self.adif_var.get().strip():
                raise ValueError("Choose an ADIF file.")
            if not self.call_var.get().strip():
                raise ValueError("Enter a callsign.")
            
            # Get current local time and convert to UTC while preserving DST
            local_now = datetime.now()  # Local time (includes DST)
            utc_now = local_now.astimezone(timezone.utc)  # Convert to UTC
            
            q = QSO(
                call=self.call_var.get().strip().upper(),
                when=utc_now,   # UTC time converted from local time
                freq_mhz=self._parse_float(self.freq_var.get()),
                band=(self.band_var.get().strip().upper() or None),
                rst_s=(self.rst_s_var.get().strip() or None),
                rst_r=(self.rst_r_var.get().strip() or None),
                tx_pwr_w=(self._parse_float(self.pwr_var.get()) if self.pwr_var.get().strip() else None),
                their_skcc=(self.their_skcc_var.get().strip().upper() or None),
                my_key=normalize(self.key_var.get()),
                country=(self.country_var.get().strip() or None),
                state=(self.state_var.get().strip().upper() or None),
            )
            fields = q.to_adif_fields()
            append_record(self.adif_var.get(), fields)
            
            # Create backup after successful save
            backup_manager.create_backup(self.adif_var.get())
            
            # Add the QSO to the recent QSOs view
            self._add_qso_to_view(q)
            
            messagebox.showinfo("Saved", f"QSO with {q.call} appended to ADIF file.\nCountry: {q.country}\nState: {q.state}")
            self._clear_fields()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _clear_fields(self):
        self.call_var.set("")
        self.freq_var.set("")
        self.band_var.set("")
        self.rst_s_var.set("599")
        self.rst_r_var.set("599")
        self.their_skcc_var.set("")
        self.country_var.set("")
        self.state_var.set("")

    def _parse_float(self, s):
        if not s.strip():
            return None
        return float(s)

    def _add_qso_to_view(self, qso):
        """Add a new QSO to the recent QSOs view."""
        try:
            # Format the QSO data for display
            # Display local time (convert from UTC)
            if qso.when:
                local_time = qso.when.astimezone()  # Convert UTC to local time
                time_str = local_time.strftime("%m/%d %H:%M")
            else:
                time_str = ""
                
            call = qso.call or ""
            band = qso.band or ""
            skcc = qso.their_skcc or ""
            # Map key types to display labels
            key_display = {
                "straight": "Straight",
                "bug": "Bug", 
                "sideswiper": "Sideswiper"
            }
            key = key_display.get(qso.my_key.value.lower() if qso.my_key else "", "")
            
            # Insert at the top of the list
            self.qso_tree.insert('', 0, values=(time_str, call, band, skcc, key))
            
            # Remove oldest entries to keep only 15
            children = self.qso_tree.get_children()
            if len(children) > 15:
                for item in children[15:]:
                    self.qso_tree.delete(item)
                    
        except Exception as e:
            print(f"Error adding QSO to view: {e}")

    def _quit(self):
        self.winfo_toplevel().destroy()

    def _configure_backup(self):
        """Simple backup configuration dialog."""
        config_window = tk.Toplevel(self.winfo_toplevel())
        config_window.title("Backup Configuration")
        config_window.geometry("500x200")
        config_window.resizable(False, False)
        
        main_frame = ttk.Frame(config_window, padding=12)
        main_frame.pack(fill="both", expand=True)
        
        # Enable backup checkbox
        backup_enabled_var = tk.BooleanVar(value=self.backup_config.get("backup_enabled", True))
        ttk.Checkbutton(main_frame, text="Enable automatic backups", 
                       variable=backup_enabled_var).pack(anchor="w", pady=5)
        
        # Backup folder
        ttk.Label(main_frame, text="Backup folder:").pack(anchor="w", pady=(10, 2))
        
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill="x", pady=2)
        
        backup_folder_var = tk.StringVar(value=self.backup_config.get("backup_folder", ""))
        ttk.Entry(folder_frame, textvariable=backup_folder_var, width=50).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(folder_frame, text="Browse", 
                  command=lambda: self._browse_folder(backup_folder_var)).pack(side="right")
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        
        def save_config():
            self.backup_config["backup_enabled"] = backup_enabled_var.get()
            self.backup_config["backup_folder"] = backup_folder_var.get()
            
            # Save to file
            self.backup_config_file.parent.mkdir(exist_ok=True)
            with open(self.backup_config_file, 'w') as f:
                json.dump(self.backup_config, f, indent=2)
            
            config_window.destroy()
            messagebox.showinfo("Saved", "Backup configuration saved.")
        
        ttk.Button(btn_frame, text="Save", command=save_config).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=config_window.destroy).pack(side="left")

    def _browse_folder(self, var):
        """Browse for a folder and update the variable."""
        folder = filedialog.askdirectory(title="Select backup folder")
        if folder:
            var.set(folder)

def main():
    root = tk.Tk()
    root.title("W4GNS SKCC Logger")
    root.geometry("600x750")
    
    app = QSOForm(root)
    root.mainloop()

if __name__ == "__main__":
    main()
