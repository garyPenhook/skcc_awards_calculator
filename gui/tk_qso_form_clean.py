#!/usr/bin/env python3
"""Clean QSO Form with Country/State Support."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timezone
import sys
import threading
import json
import shutil
import asyncio
from pathlib import Path
from typing import Optional

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.key_type import KeyType, DISPLAY_LABELS, normalize
from models.qso import QSO
from adif_io.adif_writer import append_record
from utils.roster_manager import RosterManager
from utils.backup_manager import backup_manager
from utils.cluster_client import SKCCClusterClient, ClusterSpot

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
        
        # Center on parent
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        # Create widgets
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        ttk.Label(main_frame, text="W4GNS SKCC Logger", 
                 font=("Arial", 14, "bold")).pack(pady=(0, 10))
        
        self.status_label = ttk.Label(main_frame, text="Checking member roster...")
        self.status_label.pack(pady=5)
        
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill="x", pady=10)
        self.progress.start()
        
        self.detail_label = ttk.Label(main_frame, text="", foreground="gray")
        self.detail_label.pack(pady=5)
        
        # Status text area
        self.status_text = tk.Text(main_frame, height=4, width=50, font=("Consolas", 8))
        self.status_text.pack(fill="both", expand=True, pady=(10, 0))
        
        # Close button (initially hidden)
        self.close_button = ttk.Button(main_frame, text="Close", command=self.close)
        self.close_button.pack_forget()  # Hidden initially
        
    def update_status(self, message, detail=""):
        """Update the status message and details."""
        if not self.dialog:
            return
            
        self.status_label.config(text=message)
        if detail:
            self.detail_label.config(text=detail)
        
        # Add to status log
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        if detail:
            self.status_text.insert(tk.END, f"           {detail}\n")
        self.status_text.see(tk.END)
        self.dialog.update()
        
    def show_final_status(self, message, detail=""):
        """Show final status and enable close button."""
        if not self.dialog:
            return
            
        self.update_status(message, detail)
        self.progress.stop()
        self.close_button.pack(pady=(10, 0))  # Show close button
        
    def close(self):
        """Close the progress dialog."""
        try:
            if hasattr(self, 'progress') and self.progress:
                self.progress.stop()
            if hasattr(self, 'dialog') and self.dialog:
                self.dialog.destroy()
                self.dialog = None
        except tk.TclError:
            # Dialog already destroyed
            pass

class QSOForm(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master, padding=12)
        self.pack(fill="both", expand=True)
        
        # QSO timing tracking
        self.qso_start_time = None  # Will be set when callsign is entered
        
        # Cluster client initialization
        self.cluster_client = None
        
        # Show progress dialog during initialization
        self.progress_dialog = RosterProgressDialog(master)
        
        # Initialize roster manager with progress updates
        self._initialize_roster()
        
        # Initialize backup configuration
        self.backup_config_file = Path.home() / ".skcc_awards" / "backup_config.json"
        self.backup_config = self._load_backup_config()
        
        self._build_widgets()
        self._update_time_display()
        
        # Close progress dialog
        self.progress_dialog.close()

    def __del__(self):
        """Cleanup when the form is destroyed."""
        if hasattr(self, 'cluster_client') and self.cluster_client:
            self.cluster_client.disconnect()

    def _initialize_roster(self):
        """Initialize roster manager with progress updates."""
        try:
            self.progress_dialog.update_status("Initializing roster manager...")
            self.roster_manager = RosterManager()
            
            # Get current roster status
            status = self.roster_manager.get_status()
            member_count = status.get('member_count', 0)
            last_update = status.get('last_update')
            needs_update = status.get('needs_update', False)
            
            if last_update:
                if isinstance(last_update, str):
                    try:
                        last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                        last_update_str = last_update_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Could not parse date {last_update}: {e}")
                        last_update_str = str(last_update)
                else:
                    last_update_str = last_update.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                last_update_str = "Never"
            
            self.progress_dialog.update_status(
                "Roster status checked", 
                f"Members: {member_count:,} | Last update: {last_update_str}"
            )
            
            # Check for roster updates on every startup (1-hour minimum interval)
            # This ensures the roster is checked more frequently than the default 24-hour interval
            self.progress_dialog.update_status("Checking for roster updates...")
            # Run roster update in a thread to avoid blocking UI
            self._update_roster_async()
                
        except Exception as e:
            self.progress_dialog.update_status(
                f"Roster initialization error: {e}",
                "Continuing without roster auto-fill"
            )
            # Create a minimal roster manager or use a dummy
            try:
                self.roster_manager = RosterManager()
            except Exception as e:
                print(f"Warning: Could not create roster manager: {e}")
                # Create a dummy roster manager that won't crash
                class DummyRosterManager:
                    def lookup_member(self, call): return None
                    def search_callsigns(self, prefix, limit=10): return []
                    async def ensure_roster_updated(self, force=False, progress_callback=None, max_age_hours=24):
                        return False, "No roster manager available"
                    def get_status(self):
                        return {'member_count': 0, 'last_update': None, 'needs_update': False}
                self.roster_manager = DummyRosterManager()
                
    def _update_roster_async(self):
        """Update roster in background with progress updates."""
        # Only update if we have a real roster manager
        if not hasattr(self.roster_manager, 'ensure_roster_updated'):
            self.progress_dialog.update_status("Roster update skipped", "No roster manager available")
            return
            
        def update_worker():
            def progress_callback(message):
                # Schedule UI update on main thread
                self.after(0, lambda: self.progress_dialog.update_status("Updating roster...", message))
            
            loop = None
            try:
                # Use asyncio to run the async roster update
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                success, message = loop.run_until_complete(
                    self.roster_manager.ensure_roster_updated(
                        force=False, 
                        progress_callback=progress_callback,
                        max_age_hours=1  # Check for updates every hour on startup
                    )
                )
                
                if success:
                    status = self.roster_manager.get_status()
                    member_count = status.get('member_count', 0)
                    last_update = status.get('last_update')
                    
                    # Format last update time
                    if last_update:
                        try:
                            if isinstance(last_update, str):
                                last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                            else:
                                last_update_dt = last_update
                            last_update_str = last_update_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                        except:
                            last_update_str = str(last_update)
                    else:
                        last_update_str = "Never"
                    
                    # Schedule UI update on main thread
                    self.after(0, lambda: self.progress_dialog.show_final_status(
                        "Roster update completed",
                        f"Ready with {member_count:,} members | Updated: {last_update_str}"
                    ))
                    # Auto-close after showing status for a few seconds and update display
                    def close_and_update():
                        self.progress_dialog.close()
                        self._update_roster_status_display()
                    self.after(3000, close_and_update)
                else:
                    # Schedule UI update on main thread
                    self.after(0, lambda: self.progress_dialog.show_final_status(
                        "Roster update failed",
                        message
                    ))
                    
            except Exception as e:
                # Schedule UI update on main thread
                self.after(0, lambda: self.progress_dialog.update_status(
                    "Roster update error",
                    str(e)
                ))
            finally:
                if loop:
                    loop.close()
        
        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=update_worker, daemon=True)
        thread.start()

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
        # Configure main grid weights for responsive layout
        self.columnconfigure(0, weight=1)  # Left panel
        self.columnconfigure(1, weight=1)  # Right panel
        self.rowconfigure(0, weight=1)
        
        # Create main left and right frames
        left_frame = ttk.LabelFrame(self, text="QSO Entry", padding=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        
        # Configure left frame for form elements
        left_frame.columnconfigure(1, weight=1)
        
        # Build QSO form in left frame
        self._build_qso_form(left_frame)
        
        # Build right panel with QSO history and cluster spots
        self._build_right_panel(right_frame)
        
    def _build_qso_form(self, parent):
        """Build the QSO entry form in the left panel."""
        r = 0
        
        # File selection
        ttk.Label(parent, text="ADIF Log File").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        file_frame = ttk.Frame(parent)
        file_frame.grid(row=r, column=1, sticky="ew", padx=6, pady=4)
        self.adif_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.adif_var, width=40).pack(side=tk.LEFT, padx=(0, 6), fill="x", expand=True)
        ttk.Button(file_frame, text="Browse", command=self._browse_adif).pack(side=tk.RIGHT)
        r += 1

        # Time display
        ttk.Label(parent, text="QSO Time:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.time_display_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.time_display_var, foreground="green").grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Call with auto-complete
        ttk.Label(parent, text="Call").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.call_var = tk.StringVar()
        self.call_entry = ttk.Entry(parent, textvariable=self.call_var, width=20)
        self.call_entry.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.call_var.trace_add('write', self._on_callsign_change)
        
        # Auto-complete listbox (initially hidden)
        self.autocomplete_frame = ttk.Frame(parent)
        self.autocomplete_listbox = tk.Listbox(self.autocomplete_frame, height=5, width=30)
        self.autocomplete_listbox.bind('<Double-Button-1>', self._select_autocomplete)
        r += 1

        # Freq & Band
        ttk.Label(parent, text="Freq (MHz)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.freq_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.freq_var, width=10).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        ttk.Label(parent, text="Band (e.g. 40M)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.band_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.band_var, width=10).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Reports
        ttk.Label(parent, text="RST sent").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.rst_s_var = tk.StringVar(value="599")
        ttk.Entry(parent, textvariable=self.rst_s_var, width=6).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        ttk.Label(parent, text="RST rcvd").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.rst_r_var = tk.StringVar(value="599")
        ttk.Entry(parent, textvariable=self.rst_r_var, width=6).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Power
        ttk.Label(parent, text="Power (W)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.pwr_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.pwr_var, width=6).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # SKCC numbers
        ttk.Label(parent, text="Their SKCC #").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.their_skcc_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.their_skcc_var, width=12).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Country (auto-filled from callsign)
        ttk.Label(parent, text="Country").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.country_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.country_var, width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # State (manual entry for US stations)
        ttk.Label(parent, text="State/Province").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.state_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.state_var, width=8).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # Key used (REQUIRED for Triple Key)
        ttk.Label(parent, text="Key used").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.key_var = tk.StringVar()
        options = [
            DISPLAY_LABELS[KeyType.STRAIGHT],
            DISPLAY_LABELS[KeyType.BUG],
            DISPLAY_LABELS[KeyType.SIDESWIPER],
        ]
        self.key_combo = ttk.Combobox(parent, textvariable=self.key_var, values=options, state="readonly", width=20)
        self.key_combo.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.key_combo.current(0)
        r += 1

        # Buttons
        btn_row = ttk.Frame(parent)
        btn_row.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_row, text="Save QSO", command=self._save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Backup Config", command=self._configure_backup).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Quit", command=self._quit).pack(side=tk.LEFT, padx=6)
        r += 1

        # Roster status display
        ttk.Label(parent, text="Roster Status:").grid(row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(20, 5))
        r += 1
        
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=r, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        
        self.roster_status_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.roster_status_var, 
                 foreground="blue", font=("Arial", 9)).pack(anchor="w")
        
        # Update roster status display
        self._update_roster_status_display()
        
    def _build_right_panel(self, parent):
        """Build the right panel with recent QSOs and cluster spots."""
        # Configure right panel grid
        parent.rowconfigure(0, weight=1)  # Recent QSOs
        parent.rowconfigure(1, weight=1)  # Cluster spots
        parent.columnconfigure(0, weight=1)
        
        # Recent QSOs section (top half of right panel)
        qso_frame = ttk.LabelFrame(parent, text="Recent QSOs", padding=10)
        qso_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        qso_frame.columnconfigure(0, weight=1)
        qso_frame.rowconfigure(0, weight=1)
        
        # Create treeview for recent QSOs
        columns = ("Time", "Call", "Band", "SKCC", "Key")
        self.qso_tree = ttk.Treeview(qso_frame, columns=columns, show="headings", height=8)
        
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
        
        # Add scrollbar for QSO treeview
        qso_scrollbar = ttk.Scrollbar(qso_frame, orient=tk.VERTICAL, command=self.qso_tree.yview)
        self.qso_tree.configure(yscrollcommand=qso_scrollbar.set)
        
        # Pack QSO treeview and scrollbar
        self.qso_tree.grid(row=0, column=0, sticky="nsew")
        qso_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Cluster spots section (bottom half of right panel)
        cluster_frame = ttk.LabelFrame(parent, text="SKCC Cluster Spots", padding=10)
        cluster_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        cluster_frame.columnconfigure(0, weight=1)
        cluster_frame.rowconfigure(1, weight=1)  # Spots tree gets the space
        
        # Cluster control frame
        cluster_control_frame = ttk.Frame(cluster_frame)
        cluster_control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        self.cluster_connect_btn = ttk.Button(cluster_control_frame, text="Connect to Cluster", command=self._toggle_cluster)
        self.cluster_connect_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cluster_status_var = tk.StringVar(value="Disconnected")
        self.cluster_status_label = ttk.Label(cluster_control_frame, textvariable=self.cluster_status_var, 
                 foreground="red", font=("Arial", 9))
        self.cluster_status_label.pack(side=tk.LEFT)
        
        # Cluster spots treeview
        spots_columns = ("Time", "Call", "Freq", "Band", "Spotter", "SNR")
        self.spots_tree = ttk.Treeview(cluster_frame, columns=spots_columns, show="headings", height=8)
        
        # Configure spots column headings and widths
        self.spots_tree.heading("Time", text="Time UTC")
        self.spots_tree.heading("Call", text="Call")
        self.spots_tree.heading("Freq", text="Freq (MHz)")
        self.spots_tree.heading("Band", text="Band")
        self.spots_tree.heading("Spotter", text="Spotter")
        self.spots_tree.heading("SNR", text="SNR")
        
        self.spots_tree.column("Time", width=70, minwidth=60)
        self.spots_tree.column("Call", width=90, minwidth=80)
        self.spots_tree.column("Freq", width=100, minwidth=90)  # Wider for 3 decimal places
        self.spots_tree.column("Band", width=60, minwidth=50)
        self.spots_tree.column("Spotter", width=100, minwidth=80)
        self.spots_tree.column("SNR", width=60, minwidth=40)
        
        # Add scrollbar for spots treeview
        spots_scrollbar = ttk.Scrollbar(cluster_frame, orient=tk.VERTICAL, command=self.spots_tree.yview)
        self.spots_tree.configure(yscrollcommand=spots_scrollbar.set)
        
        # Pack spots treeview and scrollbar
        self.spots_tree.grid(row=1, column=0, sticky="nsew")
        spots_scrollbar.grid(row=1, column=1, sticky="ns")
        
        # Bind double-click to auto-fill frequency
        self.spots_tree.bind('<Double-Button-1>', self._on_spot_double_click)

    def _update_roster_status_display(self):
        """Update the roster status display in the main form."""
        try:
            if hasattr(self.roster_manager, 'get_status'):
                status = self.roster_manager.get_status()
                member_count = status.get('member_count', 0)
                last_update = status.get('last_update')
                
                if last_update:
                    try:
                        if isinstance(last_update, str):
                            last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                        else:
                            last_update_dt = last_update
                        last_update_str = last_update_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except:
                        last_update_str = str(last_update)
                else:
                    last_update_str = "Never updated"
                
                status_text = f"Members: {member_count:,} | Last updated: {last_update_str}"
                self.roster_status_var.set(status_text)
            else:
                self.roster_status_var.set("Roster manager not available")
        except Exception as e:
            self.roster_status_var.set(f"Status error: {e}")

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
            
            if self.qso_start_time:
                # QSO in progress - show duration
                duration = utc_now - self.qso_start_time
                duration_minutes = int(duration.total_seconds() / 60)
                duration_seconds = int(duration.total_seconds() % 60)
                
                display_time = (f"QSO in progress: {duration_minutes:02d}:{duration_seconds:02d} "
                               f"(Started: {self.qso_start_time.strftime('%H:%M:%S UTC')})")
                self.time_display_var.set(display_time)
            else:
                # No QSO in progress - show current time
                display_time = f"{now.strftime('%H:%M:%S')} local ({utc_now.strftime('%H:%M:%S')} UTC)"
                self.time_display_var.set(display_time)
                
            self.after(1000, self._update_time_display)
        except Exception as e:
            print(f"Time display error: {e}")
            self.after(5000, self._update_time_display)

    def _on_callsign_change(self, *args):
        """Handle callsign field changes for auto-complete and country lookup."""
        callsign = self.call_var.get().upper().strip()
        
        # Capture QSO start time when callsign is first entered
        if callsign and self.qso_start_time is None:
            self.qso_start_time = datetime.now().astimezone(timezone.utc)
            print(f"QSO started with {callsign} at {self.qso_start_time.strftime('%H:%M:%S UTC')}")
        
        # Reset start time if callsign is cleared
        if not callsign:
            self.qso_start_time = None
        
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
            
            # Get current local time and convert to UTC for end time
            local_now = datetime.now()  # Local time (includes DST)
            utc_end_time = local_now.astimezone(timezone.utc)  # Convert to UTC
            
            # Use the captured start time, or current time if none captured
            if self.qso_start_time:
                start_utc = self.qso_start_time
            else:
                # No start time captured (shouldn't happen), use current time
                start_utc = utc_end_time
                print("Warning: No QSO start time captured, using current time")
            
            q = QSO(
                call=self.call_var.get().strip().upper(),
                when=start_utc,      # QSO start time (when callsign was entered)
                time_off=utc_end_time,  # QSO end time (when Save was pressed)
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
            
            # Calculate QSO duration for display
            duration = utc_end_time - start_utc
            duration_minutes = int(duration.total_seconds() / 60)
            duration_seconds = int(duration.total_seconds() % 60)
            
            fields = q.to_adif_fields()
            append_record(self.adif_var.get(), fields)
            
            # Create backup after successful save
            backup_manager.create_backup(self.adif_var.get())
            
            # Add the QSO to the recent QSOs view
            self._add_qso_to_view(q)
            
            # Enhanced save message with duration info
            duration_text = f"Duration: {duration_minutes:02d}:{duration_seconds:02d}" if duration_minutes > 0 or duration_seconds > 0 else "Duration: <1 sec"
            messagebox.showinfo("Saved", 
                f"QSO with {q.call} saved to ADIF file.\n"
                f"{duration_text}\n"
                f"Country: {q.country}\n"
                f"State: {q.state}\n"
                f"Start: {start_utc.strftime('%H:%M:%S UTC')}\n"
                f"End: {utc_end_time.strftime('%H:%M:%S UTC')}")
            
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
        
        # Reset QSO start time for next QSO
        self.qso_start_time = None

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

    def _toggle_cluster(self):
        """Toggle cluster connection on/off."""
        if self.cluster_client and self.cluster_client.connected:
            # Disconnect
            self.cluster_client.disconnect()
            self.cluster_client = None
            self.cluster_connect_btn.config(text="Connect to Cluster")
            self.cluster_status_var.set("Disconnected")
            self.cluster_status_label.config(foreground="red")
        else:
            # Connect - prompt for callsign
            callsign = self._get_cluster_callsign()
            if not callsign:
                return
                
            self.cluster_client = SKCCClusterClient(callsign, self._on_new_spot)
            
            if self.cluster_client.connect():
                self.cluster_connect_btn.config(text="Disconnect")
                self.cluster_status_var.set(f"Connected as {callsign}")
                self.cluster_status_label.config(foreground="green")
            else:
                self.cluster_client = None
                self.cluster_status_var.set("Connection failed")
                self.cluster_status_label.config(foreground="red")

    def _on_new_spot(self, spot: ClusterSpot):
        """Handle new cluster spot."""
        # Use after() to safely update GUI from background thread
        self.after(0, self._add_spot_to_tree, spot)

    def _add_spot_to_tree(self, spot: ClusterSpot):
        """Add a new spot to the spots treeview (thread-safe)."""
        try:
            # Format values for display
            time_str = spot.time_utc.strftime("%H:%M")
            freq_str = f"{spot.frequency:.3f}"  # Show 3 decimal places for accuracy
            snr_str = f"{spot.snr}dB" if spot.snr else ""
            
            # Check for existing spots from the same callsign and remove them
            duplicate_found = False
            children = self.spots_tree.get_children()
            for child in children:
                values = self.spots_tree.item(child, 'values')
                if values and len(values) > 1 and values[1] == spot.callsign:
                    # Found duplicate callsign - remove the older spot
                    old_freq = values[2] if len(values) > 2 else "unknown"
                    print(f"Duplicate filter: Replacing {spot.callsign} {old_freq} MHz with {freq_str} MHz")
                    self.spots_tree.delete(child)
                    duplicate_found = True
            
            # Insert new spot at the top of the tree
            item = self.spots_tree.insert("", 0, values=(
                time_str, spot.callsign, freq_str, spot.band, spot.spotter, snr_str
            ))
            
            if not duplicate_found:
                print(f"New spot: {spot.callsign} {freq_str} MHz {spot.band} ({spot.spotter})")
            
            # Keep only the last 50 spots to avoid memory issues
            children = self.spots_tree.get_children()
            if len(children) > 50:
                for child in children[50:]:
                    self.spots_tree.delete(child)
                    
            # Auto-scroll to show new spot
            self.spots_tree.see(item)
            
        except Exception as e:
            print(f"Error adding spot to tree: {e}")

    def _on_spot_double_click(self, event):
        """Handle double-click on a cluster spot to auto-fill frequency."""
        try:
            item = self.spots_tree.selection()[0]
            values = self.spots_tree.item(item, 'values')
            
            if values:
                callsign = values[1]
                frequency = values[2]
                band = values[3]
                
                # Auto-fill the form
                self.call_var.set(callsign)
                self.freq_var.set(frequency)
                self.band_var.set(band)
                
                # Focus on the call entry to trigger any auto-fill logic
                self.call_entry.focus_set()
                
                print(f"Auto-filled from spot: {callsign} on {frequency} MHz ({band})")
                
        except (IndexError, Exception) as e:
            print(f"Error handling spot double-click: {e}")

    def _get_cluster_callsign(self) -> Optional[str]:
        """Prompt user for cluster callsign."""
        from tkinter import simpledialog
        
        callsign = simpledialog.askstring(
            "Cluster Connection",
            "Enter your callsign for cluster connection:\n(e.g., W4GNS-SKCC)",
            initialvalue="W4GNS-SKCC"
        )
        
        if callsign:
            return callsign.upper().strip()
        return None

def main():
    root = tk.Tk()
    root.title("W4GNS SKCC Logger - Enhanced with Cluster Spots")
    root.geometry("1200x700")  # Wider layout for two-column design
    root.minsize(1000, 600)    # Minimum size to see all features
    
    app = QSOForm(root)
    root.mainloop()

if __name__ == "__main__":
    main()
