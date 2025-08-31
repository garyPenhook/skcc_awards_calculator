import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timezone
import sys
import threading
from pathlib import Path

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.key_type import KeyType, DISPLAY_LABELS, normalize
from models.qso import QSO
from adif_io.adif_writer import append_record
from utils.theme_manager import theme_manager
from utils.roster_manager import RosterManager
from utils.backup_manager import backup_manager

class QSOForm(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master, padding=12)
        self.grid(sticky="nsew")
        
        # Initialize roster manager
        self.roster_manager = RosterManager()
        self.roster_status = "Initializing..."
        
        # Option to control roster update behavior
        # Set to False if you want to use cached roster (faster startup)
        self.force_roster_update = True
        
        # Apply theme to the parent window
        if master:
            theme_manager.apply_theme(master)
            
        self._build_ui()
        
        # Delay roster update until the main loop is running
        self.after(1000, self._start_roster_update)  # Start after 1 second

    def _build_ui(self):
        r = 0
        
        # Roster status
        ttk.Label(self, text="Roster Status:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.roster_status_var = tk.StringVar(value=self.roster_status)
        ttk.Label(self, textvariable=self.roster_status_var, foreground="blue").grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1
        
        # ADIF path
        ttk.Label(self, text="ADIF file").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.adif_var = tk.StringVar()
        adif_entry = ttk.Entry(self, textvariable=self.adif_var, width=50)
        adif_entry.grid(row=r, column=1, sticky="we", padx=6, pady=4)
        
        # File operation buttons
        file_buttons = ttk.Frame(self)
        file_buttons.grid(row=r, column=2, padx=6, pady=4)
        ttk.Button(file_buttons, text="Open", command=self._open_adif).grid(row=0, column=0, padx=(0, 2))
        ttk.Button(file_buttons, text="New", command=self._new_adif).grid(row=0, column=1, padx=2)
        r += 1
        
        # Time display (Local and UTC)
        ttk.Label(self, text="QSO Time:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.time_display_var = tk.StringVar()
        ttk.Label(self, textvariable=self.time_display_var, foreground="green").grid(row=r, column=1, sticky="w", padx=6, pady=4)
        
        # Start time updates
        self._update_time_display()
        r += 1

        # Call with auto-complete
        ttk.Label(self, text="Call").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.call_var = tk.StringVar()
        self.call_entry = ttk.Entry(self, textvariable=self.call_var, width=20)
        self.call_entry.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.call_var.trace_add('write', self._on_callsign_change)
        
        # Add focus out event to hide autocomplete
        self.call_entry.bind('<FocusOut>', self._on_callsign_focus_out)
        self.call_entry.bind('<Escape>', self._on_escape_key)
        
        # Auto-complete listbox (initially hidden)
        self.autocomplete_frame = ttk.Frame(self)
        self.autocomplete_listbox = tk.Listbox(self.autocomplete_frame, height=5, width=30)
        self.autocomplete_listbox.bind('<Double-Button-1>', self._select_autocomplete)
        self.autocomplete_listbox.bind('<Return>', self._select_autocomplete)
        self.autocomplete_listbox.bind('<Escape>', self._on_escape_key)
        
        r += 1

        # Freq & Band
        ttk.Label(self, text="Freq (MHz)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.freq_var = tk.StringVar()
        self.freq_entry = ttk.Entry(self, textvariable=self.freq_var, width=10)
        self.freq_entry.grid(row=r, column=1, sticky="w", padx=6, pady=4)
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

        # Station + Operator + Power
        ttk.Label(self, text="Station callsign").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.station_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.station_var, width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        ttk.Label(self, text="Operator").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.op_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.op_var, width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        ttk.Label(self, text="Power (W)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.pwr_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.pwr_var, width=6).grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        # SKCC numbers
        ttk.Label(self, text="Their SKCC #").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.their_skcc_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.their_skcc_var, width=12).grid(row=r, column=1, sticky="w", padx=6, pady=4)
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
        btn_row = ttk.Frame(self); btn_row.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(btn_row, text="Save QSO", command=self._save).grid(row=0, column=0, padx=6)
        
        # Backup config button
        ttk.Button(btn_row, text="Backup ⚙", command=self._show_backup_info).grid(row=0, column=1, padx=6)
        
        # Theme toggle button
        current_theme = "🌙" if theme_manager.current_theme == "light" else "☀️"
        self.theme_button = ttk.Button(btn_row, text=current_theme, width=3, command=self._toggle_theme)
        self.theme_button.grid(row=0, column=2, padx=6)
        
        ttk.Button(btn_row, text="Quit", command=self._quit).grid(row=0, column=3, padx=6)
        r += 1

        # Recent QSOs view
        ttk.Label(self, text="Recent QSOs:").grid(row=r, column=0, columnspan=3, sticky="w", padx=6, pady=(20, 5))
        r += 1
        
        # Create treeview for recent QSOs
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=r, column=0, columnspan=3, sticky="nsew", padx=6, pady=5)
        
        # Treeview with scrollbar
        self.qso_tree = ttk.Treeview(tree_frame, 
                                    columns=("time", "call", "band", "skcc", "key"), 
                                    show="headings", 
                                    height=6)
        
        # Define column headings and widths
        self.qso_tree.heading("time", text="Time (UTC)")
        self.qso_tree.heading("call", text="Call")
        self.qso_tree.heading("band", text="Band")
        self.qso_tree.heading("skcc", text="SKCC #")
        self.qso_tree.heading("key", text="Key")
        
        self.qso_tree.column("time", width=120)
        self.qso_tree.column("call", width=100)
        self.qso_tree.column("band", width=60)
        self.qso_tree.column("skcc", width=80)
        self.qso_tree.column("key", width=80)
        
        # Scrollbar for the treeview
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.qso_tree.yview)
        self.qso_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        # Pack treeview and scrollbar
        self.qso_tree.pack(side="left", fill="both", expand=True)
        tree_scrollbar.pack(side="right", fill="y")
        
        r += 1

        # Resize behavior
        for c in range(3):
            self.columnconfigure(c, weight=1)
        
        # Make the tree frame expandable
        self.rowconfigure(r-1, weight=1)

    def _start_roster_update(self):
        """Start roster update in background thread."""
        def update_roster():
            try:
                # Use after() to update GUI from background thread
                self.after(0, lambda: self.roster_status_var.set("Checking roster status..."))
                
                status = self.roster_manager.get_status()
                
                # Check if we should force update or use normal logic
                if self.force_roster_update:
                    # Always attempt to update roster on QSO logger startup for current data
                    self.after(0, lambda: self.roster_status_var.set("Downloading latest SKCC roster..."))
                    force_update = True
                elif status['needs_update']:
                    # Use normal 24-hour update logic
                    self.after(0, lambda: self.roster_status_var.set("Downloading SKCC roster..."))
                    force_update = False
                else:
                    # Roster is current, just display status
                    force_update = None
                
                if force_update is not None:
                    # Run the async update in a new event loop
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    def progress_callback(message):
                        self.after(0, lambda msg=message: self.roster_status_var.set(msg))
                    
                    # Update with appropriate force flag
                    success, message = loop.run_until_complete(
                        self.roster_manager.ensure_roster_updated(force=force_update, progress_callback=progress_callback)
                    )
                    loop.close()
                    
                    if not success:
                        # If update fails, fall back to existing data
                        self.after(0, lambda: self.roster_status_var.set("Using cached roster data"))
                        # Still show the cached data status
                        status = self.roster_manager.get_status()
                        member_count = status.get('member_count', 0)
                        if member_count > 0:
                            final_message = f"Cached roster - {member_count:,} members"
                            self.after(0, lambda: self.roster_status_var.set(final_message))
                        else:
                            self.after(0, lambda: self.roster_status_var.set(f"Roster error: {message}"))
                        return
                
                # Get final status and display
                status = self.roster_manager.get_status()
                member_count = status.get('member_count', 0)
                last_update = status.get('last_update', 'Never')
                
                if last_update != 'Never':
                    # Format the ISO date nicely
                    from datetime import datetime
                    dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    last_update = dt.strftime('%Y-%m-%d %H:%M')
                
                final_message = f"Ready - {member_count:,} members (Updated: {last_update})"
                self.after(0, lambda: self.roster_status_var.set(final_message))
                
            except Exception as e:
                error_message = f"Roster error: {str(e)}"
                self.after(0, lambda: self.roster_status_var.set(error_message))
                print(f"Roster update error: {e}")
        
        # Run in background thread
        threading.Thread(target=update_roster, daemon=True).start()

    def _update_time_display(self):
        """Update the time display showing UTC time."""
        try:
            local_now = datetime.now()
            utc_now = local_now.astimezone(timezone.utc)
            
            # Show only UTC time for amateur radio logging
            utc_str = utc_now.strftime("%H:%M:%S UTC")
            self.time_display_var.set(utc_str)
            
            # Schedule next update in 1 second
            self.after(1000, self._update_time_display)
            
        except Exception as e:
            print(f"Time display error: {e}")
            # Try again in 5 seconds if there's an error
            self.after(5000, self._update_time_display)

    def _on_callsign_change(self, *args):
        """Handle callsign field changes for auto-complete."""
        callsign = self.call_var.get().upper().strip()
        
        if len(callsign) >= 2:  # Start suggesting after 2 characters
            try:
                # Search for matching callsigns
                matches = self.roster_manager.search_callsigns(callsign, limit=10)
                
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

    def _hide_autocomplete(self):
        """Hide the autocomplete listbox."""
        self.autocomplete_frame.grid_remove()

    def _on_callsign_focus_out(self, event=None):
        """Hide autocomplete when callsign field loses focus."""
        # Small delay to allow selection to complete
        self.after(100, self._hide_autocomplete)

    def _on_escape_key(self, event=None):
        """Hide autocomplete when Escape is pressed."""
        self._hide_autocomplete()
        return 'break'  # Prevent further processing

    def _select_autocomplete(self, event=None):
        """Select an autocomplete suggestion."""
        try:
            selection = self.autocomplete_listbox.curselection()
            if selection:
                # Get the selected text and extract callsign and SKCC number
                selected_text = self.autocomplete_listbox.get(selection[0])
                callsign = selected_text.split(' - ')[0]
                skcc_number = selected_text.split('SKCC #')[1]
                
                # Fill in the callsign and SKCC number
                self.call_var.set(callsign)
                self.their_skcc_var.set(skcc_number)
                
                # Hide autocomplete
                self._hide_autocomplete()
                
                # Focus next field - we'll store a reference to the freq entry during build
                if hasattr(self, 'freq_entry'):
                    self.freq_entry.focus_set()
                
        except Exception as e:
            print(f"Selection error: {e}")
            self._hide_autocomplete()

    def _choose_adif(self):
        path = filedialog.asksaveasfilename(
            title="Select ADIF file",
            defaultextension=".adi",
            filetypes=[("ADIF files", "*.adi"), ("All files", "*.*")],
        )
        if path:
            self.adif_var.set(path)

    def _open_adif(self):
        """Open an existing ADIF file for viewing/appending."""
        path = filedialog.askopenfilename(
            title="Open existing ADIF file",
            filetypes=[("ADIF files", "*.adi"), ("All files", "*.*")],
        )
        if path:
            self.adif_var.set(path)
            self._load_adif_info(path)
            self._load_recent_qsos(path)

    def _new_adif(self):
        """Create a new ADIF file."""
        path = filedialog.asksaveasfilename(
            title="Create new ADIF file",
            defaultextension=".adi",
            filetypes=[("ADIF files", "*.adi"), ("All files", "*.*")],
        )
        if path:
            self.adif_var.set(path)
            # Clear recent QSOs view for new file
            for item in self.qso_tree.get_children():
                self.qso_tree.delete(item)

    def _load_adif_info(self, path):
        """Load and display information about the ADIF file."""
        try:
            from pathlib import Path
            
            if not Path(path).exists():
                messagebox.showwarning("File Not Found", f"ADIF file not found: {path}")
                return
                
            # Simple file statistics without parsing
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Count QSO records by looking for <EOR> tags
            import re
            eor_pattern = re.compile(r'<eor>', re.IGNORECASE)
            qso_count = len(eor_pattern.findall(content))
            
            file_size = Path(path).stat().st_size
            file_size_kb = file_size / 1024
            
            if qso_count == 0:
                messagebox.showinfo("ADIF File", 
                    f"Opened: {Path(path).name}\n"
                    f"File size: {file_size_kb:.1f} KB\n"
                    f"No QSO records found.\n\n"
                    f"You can now add QSOs to this file.")
            else:
                messagebox.showinfo("ADIF File", 
                    f"Opened: {Path(path).name}\n"
                    f"File size: {file_size_kb:.1f} KB\n"
                    f"QSO records: {qso_count}\n\n"
                    f"You can now add new QSOs to this file.")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read ADIF file: {e}")

    def _load_recent_qsos(self, path):
        """Load the last 10 QSOs from the ADIF file."""
        try:
            from pathlib import Path
            
            if not Path(path).exists():
                return
                
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse QSO records manually for display
            import re
            qso_records = []
            
            # Find all QSO records (between start and <EOR>)
            eor_pattern = re.compile(r'(.*?)<eor>', re.IGNORECASE | re.DOTALL)
            matches = eor_pattern.findall(content)
            
            for match in matches[-10:]:  # Get last 10 records
                qso_data = {}
                
                # Extract fields using regex
                field_pattern = re.compile(r'<(\w+):(\d+)>([^<]*)', re.IGNORECASE)
                fields = field_pattern.findall(match)
                
                for tag, length, value in fields:
                    qso_data[tag.upper()] = value[:int(length)] if length.isdigit() else value
                
                if 'CALL' in qso_data:  # Only add if we have a callsign
                    qso_records.append(qso_data)
            
            # Clear existing entries and populate with recent QSOs
            for item in self.qso_tree.get_children():
                self.qso_tree.delete(item)
            
            # Add QSOs to treeview (newest first)
            for qso in reversed(qso_records):
                time_str = self._format_qso_time(qso.get('QSO_DATE', ''), qso.get('TIME_ON', ''))
                call = qso.get('CALL', '')
                band = qso.get('BAND', '')
                skcc = qso.get('SKCC', qso.get('APP_SKCC', ''))
                key = qso.get('APP_SKCC_KEY', qso.get('SIG_INFO', ''))
                
                self.qso_tree.insert('', 0, values=(time_str, call, band, skcc, key))
                
        except Exception as e:
            print(f"Error loading recent QSOs: {e}")

    def _format_qso_time(self, qso_date, time_on):
        """Format QSO date and time for display."""
        try:
            if qso_date and len(qso_date) >= 8:
                date_part = f"{qso_date[4:6]}/{qso_date[6:8]}"
                if time_on and len(time_on) >= 4:
                    time_part = f"{time_on[:2]}:{time_on[2:4]}"
                    return f"{date_part} {time_part}"
                return date_part
            return ""
        except:
            return ""

    def _add_qso_to_view(self, qso):
        """Add a new QSO to the recent QSOs view."""
        try:
            # Format the QSO data for display
            # Display UTC time (which is how it's stored)
            if qso.when:
                time_str = qso.when.strftime("%m/%d %H:%M")
            else:
                time_str = ""
                
            call = qso.call or ""
            band = qso.band or ""
            skcc = qso.their_skcc or ""
            key = DISPLAY_LABELS.get(qso.my_key, str(qso.my_key)) if qso.my_key else ""
            
            # Insert at the top of the list
            self.qso_tree.insert('', 0, values=(time_str, call, band, skcc, key))
            
            # Remove oldest entries to keep only 10
            children = self.qso_tree.get_children()
            if len(children) > 10:
                for item in children[10:]:
                    self.qso_tree.delete(item)
                    
        except Exception as e:
            print(f"Error adding QSO to view: {e}")

    def _parse_float(self, s):
        if not s.strip():
            return None
        return float(s)

    def _save(self):
        try:
            if not self.adif_var.get().strip():
                raise ValueError("Choose an ADIF file.")
            if not self.call_var.get().strip():
                raise ValueError("Enter a callsign.")
            # Build QSO
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
                station_callsign=(self.station_var.get().strip().upper() or None),
                operator=(self.op_var.get().strip().upper() or None),
                tx_pwr_w=(self._parse_float(self.pwr_var.get()) if self.pwr_var.get().strip() else None),
                their_skcc=(self.their_skcc_var.get().strip().upper() or None),
                my_key=normalize(self.key_var.get()),
            )
            fields = q.to_adif_fields()
            append_record(self.adif_var.get(), fields)
            
            # Create backup after successful save
            backup_manager.create_backup(self.adif_var.get())
            
            # Add the QSO to the recent QSOs view
            self._add_qso_to_view(q)
            
            messagebox.showinfo("Saved", "QSO appended.")
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
        # keep station, op, pwr, and key selection as convenience

    def _quit(self):
        self.winfo_toplevel().destroy()

    def _toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        try:
            new_theme = theme_manager.toggle_theme()
            theme_manager.apply_theme(self.winfo_toplevel())
            
            # Update theme button icon
            new_icon = "🌙" if new_theme == "light" else "☀️"
            self.theme_button.configure(text=new_icon)
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to toggle theme: {e}")

    def _show_backup_info(self) -> None:
        """Show backup information and configuration."""
        backup_folder = backup_manager.get_backup_folder()
        is_enabled = backup_manager.config.get("backup_enabled", True)
        secondary = backup_manager.config.get("secondary_backup", "").strip()
        
        info_text = f"""Automatic Backup System

Status: {'Enabled' if is_enabled else 'Disabled'}

Primary Backup Folder:
{backup_folder}

Secondary Backup: {'Configured' if secondary else 'Not configured'}
{secondary if secondary else '(Optional - for USB/network backup)'}

Backups are created automatically when saving QSOs.
The last 10 backups are kept for each ADIF file.

To configure backup settings, edit:
{backup_manager.config_file}"""

        messagebox.showinfo("Backup Configuration", info_text)

    def _load_backup_config(self) -> dict:
        """Load backup configuration from file."""
        default_config = {
            "auto_backup": True,
            "backup_folder": str(Path.home() / ".skcc_awards" / "backups"),
            "secondary_backup": "",
            "backup_enabled": True
        }
        
        try:
            if self.backup_config_file.exists():
                with open(self.backup_config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to handle missing keys
                    return {**default_config, **config}
        except Exception:
            pass
        
        return default_config
    
    def _save_backup_config(self) -> None:
        """Save backup configuration to file."""
        try:
            self.backup_config_file.parent.mkdir(exist_ok=True)
            with open(self.backup_config_file, 'w') as f:
                json.dump(self.backup_config, f, indent=2)
        except Exception:
            pass  # Fail silently if we can't save
    
    def _create_backup(self, source_file: str) -> None:
        """Create backup of ADIF file."""
        if not self.backup_config.get("backup_enabled", True):
            return
            
        try:
            source_path = Path(source_file)
            if not source_path.exists():
                return
            
            # Create timestamp for backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source_path.stem}_backup_{timestamp}{source_path.suffix}"
            
            # Primary backup location
            backup_folder = Path(self.backup_config.get("backup_folder"))
            backup_folder.mkdir(parents=True, exist_ok=True)
            primary_backup = backup_folder / backup_name
            shutil.copy2(source_file, primary_backup)
            
            # Secondary backup location (if configured)
            secondary_path = self.backup_config.get("secondary_backup", "").strip()
            if secondary_path and Path(secondary_path).exists():
                secondary_backup = Path(secondary_path) / backup_name
                try:
                    shutil.copy2(source_file, secondary_backup)
                except Exception:
                    # Secondary backup failed, but don't stop the main operation
                    pass
                    
            # Clean up old backups (keep last 10)
            self._cleanup_old_backups(backup_folder, source_path.stem)
            
        except Exception as e:
            # Don't interrupt the save operation if backup fails
            print(f"Backup failed: {e}")
    
    def _cleanup_old_backups(self, backup_folder: Path, file_stem: str) -> None:
        """Keep only the last 10 backups for each file."""
        try:
            pattern = f"{file_stem}_backup_*"
            backups = sorted(backup_folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Remove backups beyond the 10 most recent
            for old_backup in backups[10:]:
                old_backup.unlink()
        except Exception:
            pass
    
    def _configure_backup(self) -> None:
        """Open backup configuration dialog."""
        config_window = tk.Toplevel(self.winfo_toplevel())
        config_window.title("Backup Configuration")
        config_window.geometry("500x300")
        config_window.resizable(False, False)
        
        # Apply theme
        theme_manager.apply_theme(config_window)
        
        main_frame = ttk.Frame(config_window, padding=12)
        main_frame.pack(fill="both", expand=True)
        
        r = 0
        
        # Enable backup checkbox
        backup_enabled_var = tk.BooleanVar(value=self.backup_config.get("backup_enabled", True))
        ttk.Checkbutton(main_frame, text="Enable automatic backups", 
                       variable=backup_enabled_var).grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
        r += 1
        
        # Primary backup folder
        ttk.Label(main_frame, text="Primary backup folder:").grid(row=r, column=0, sticky="w", pady=4)
        r += 1
        
        backup_folder_var = tk.StringVar(value=self.backup_config.get("backup_folder"))
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        
        ttk.Entry(folder_frame, textvariable=backup_folder_var, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_frame, text="Browse", 
                  command=lambda: self._browse_folder(backup_folder_var)).pack(side="right", padx=(4, 0))
        r += 1
        
        # Secondary backup location
        ttk.Label(main_frame, text="Secondary backup (USB/Network):").grid(row=r, column=0, sticky="w", pady=(12, 4))
        r += 1
        
        secondary_var = tk.StringVar(value=self.backup_config.get("secondary_backup", ""))
        secondary_frame = ttk.Frame(main_frame)
        secondary_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        
        ttk.Entry(secondary_frame, textvariable=secondary_var, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(secondary_frame, text="Browse", 
                  command=lambda: self._browse_folder(secondary_var)).pack(side="right", padx=(4, 0))
        r += 1
        
        # Info label
        info_text = ("Backups are created automatically when saving QSOs.\n" +
                    "Primary backups are always created locally.\n" +
                    "Secondary backup is optional (e.g., USB stick for safety).\n" +
                    "Only the 10 most recent backups are kept.")
        ttk.Label(main_frame, text=info_text, foreground="gray").grid(row=r, column=0, columnspan=2, sticky="w", pady=(12, 4))
        r += 1
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        
        def save_config():
            self.backup_config.update({
                "backup_enabled": backup_enabled_var.get(),
                "backup_folder": backup_folder_var.get(),
                "secondary_backup": secondary_var.get()
            })
            self._save_backup_config()
            config_window.destroy()
            messagebox.showinfo("Saved", "Backup configuration saved.")
        
        ttk.Button(btn_frame, text="Save", command=save_config).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=config_window.destroy).pack(side="left")
        
        main_frame.columnconfigure(0, weight=1)
    
    def _browse_folder(self, var: tk.StringVar) -> None:
        """Browse for a folder and update the variable."""
        folder = filedialog.askdirectory(title="Select backup folder")
        if folder:
            var.set(folder)

def main():
    root = tk.Tk()
    root.title("SKCC QSO Logger - Open/Create ADIF Files")
    # tk scaling & theming are optional; keep it simple
    frm = QSOForm(root)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    
    # Show help message after a brief delay
    def show_help():
        messagebox.showinfo("SKCC QSO Logger", 
            "Welcome to the SKCC QSO Logger!\n\n" +
            "• Click 'Open' to load an existing ADIF file\n" +
            "• Click 'New' to create a new ADIF file\n" +
            "• Fill in QSO details and click 'Save QSO'\n" +
            "• Type callsigns to see auto-complete suggestions\n\n" +
            "Features:\n" +
            "• Downloads latest SKCC roster on startup\n" +
            "• Auto-complete with 30,000+ SKCC members\n" +
            "• Recent QSOs view at bottom\n" +
            "• Proper UTC time handling\n\n" +
            "The logger supports ADIF 3.1.5 format with SKCC-specific fields.")
    
    def _load_backup_config(self) -> dict:
        """Load backup configuration from file."""
        default_config = {
            "auto_backup": True,
            "backup_folder": str(Path.home() / ".skcc_awards" / "backups"),
            "secondary_backup": "",
            "backup_enabled": True
        }
        
        try:
            if self.backup_config_file.exists():
                with open(self.backup_config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to handle missing keys
                    return {**default_config, **config}
        except Exception:
            pass
        
        return default_config
    
    def _save_backup_config(self) -> None:
        """Save backup configuration to file."""
        try:
            self.backup_config_file.parent.mkdir(exist_ok=True)
            with open(self.backup_config_file, 'w') as f:
                json.dump(self.backup_config, f, indent=2)
        except Exception:
            pass  # Fail silently if we can't save
    
    def _create_backup(self, source_file: str) -> None:
        """Create backup of ADIF file."""
        if not self.backup_config.get("backup_enabled", True):
            return
            
        try:
            source_path = Path(source_file)
            if not source_path.exists():
                return
            
            # Create timestamp for backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source_path.stem}_backup_{timestamp}{source_path.suffix}"
            
            # Primary backup location
            backup_folder = Path(self.backup_config.get("backup_folder"))
            backup_folder.mkdir(parents=True, exist_ok=True)
            primary_backup = backup_folder / backup_name
            shutil.copy2(source_file, primary_backup)
            
            # Secondary backup location (if configured)
            secondary_path = self.backup_config.get("secondary_backup", "").strip()
            if secondary_path and Path(secondary_path).exists():
                secondary_backup = Path(secondary_path) / backup_name
                try:
                    shutil.copy2(source_file, secondary_backup)
                except Exception:
                    # Secondary backup failed, but don't stop the main operation
                    pass
                    
            # Clean up old backups (keep last 10)
            self._cleanup_old_backups(backup_folder, source_path.stem)
            
        except Exception as e:
            # Don't interrupt the save operation if backup fails
            print(f"Backup failed: {e}")
    
    def _cleanup_old_backups(self, backup_folder: Path, file_stem: str) -> None:
        """Keep only the last 10 backups for each file."""
        try:
            pattern = f"{file_stem}_backup_*"
            backups = sorted(backup_folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Remove backups beyond the 10 most recent
            for old_backup in backups[10:]:
                old_backup.unlink()
        except Exception:
            pass
    
    def _configure_backup(self) -> None:
        """Open backup configuration dialog."""
        config_window = tk.Toplevel(self.winfo_toplevel())
        config_window.title("Backup Configuration")
        config_window.geometry("500x300")
        config_window.resizable(False, False)
        
        # Apply theme
        theme_manager.apply_theme(config_window)
        
        main_frame = ttk.Frame(config_window, padding=12)
        main_frame.pack(fill="both", expand=True)
        
        r = 0
        
        # Enable backup checkbox
        backup_enabled_var = tk.BooleanVar(value=self.backup_config.get("backup_enabled", True))
        ttk.Checkbutton(main_frame, text="Enable automatic backups", 
                       variable=backup_enabled_var).grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
        r += 1
        
        # Primary backup folder
        ttk.Label(main_frame, text="Primary backup folder:").grid(row=r, column=0, sticky="w", pady=4)
        r += 1
        
        backup_folder_var = tk.StringVar(value=self.backup_config.get("backup_folder"))
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        
        ttk.Entry(folder_frame, textvariable=backup_folder_var, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_frame, text="Browse", 
                  command=lambda: self._browse_folder(backup_folder_var)).pack(side="right", padx=(4, 0))
        r += 1
        
        # Secondary backup location
        ttk.Label(main_frame, text="Secondary backup (USB/Network):").grid(row=r, column=0, sticky="w", pady=(12, 4))
        r += 1
        
        secondary_var = tk.StringVar(value=self.backup_config.get("secondary_backup", ""))
        secondary_frame = ttk.Frame(main_frame)
        secondary_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        
        ttk.Entry(secondary_frame, textvariable=secondary_var, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(secondary_frame, text="Browse", 
                  command=lambda: self._browse_folder(secondary_var)).pack(side="right", padx=(4, 0))
        r += 1
        
        # Info label
        info_text = ("Backups are created automatically when saving QSOs.\n" +
                    "Primary backups are always created locally.\n" +
                    "Secondary backup is optional (e.g., USB stick for safety).\n" +
                    "Only the 10 most recent backups are kept.")
        ttk.Label(main_frame, text=info_text, foreground="gray").grid(row=r, column=0, columnspan=2, sticky="w", pady=(12, 4))
        r += 1
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        
        def save_config():
            self.backup_config.update({
                "backup_enabled": backup_enabled_var.get(),
                "backup_folder": backup_folder_var.get(),
                "secondary_backup": secondary_var.get()
            })
            self._save_backup_config()
            config_window.destroy()
            messagebox.showinfo("Saved", "Backup configuration saved.")
        
        ttk.Button(btn_frame, text="Save", command=save_config).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=config_window.destroy).pack(side="left")
        
        main_frame.columnconfigure(0, weight=1)
    
    def _browse_folder(self, var: tk.StringVar) -> None:
        """Browse for a folder and update the variable."""
        folder = filedialog.askdirectory(title="Select backup folder")
        if folder:
            var.set(folder)

def main():
    root = tk.Tk()
    root.title("SKCC QSO Logger - Open/Create ADIF Files")
    # tk scaling & theming are optional; keep it simple
    frm = QSOForm(root)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    
    def show_help():
        messagebox.showinfo("SKCC QSO Logger Help",
            "Welcome to the SKCC QSO Logger!\n\n" +
            "Features:\n" +
            "• Live roster integration with 30,000+ SKCC members\n" +
            "• Auto-complete with 30,000+ SKCC members\n" +
            "• Recent QSOs view at bottom\n" +
            "• Proper UTC time handling\n" +
            "• Automatic backup system\n\n" +
            "The logger supports ADIF 3.1.5 format with SKCC-specific fields.")
    
    root.after(2000, show_help)  # Show help after 2 seconds
    
    root.mainloop()

if __name__ == "__main__":
    main()
