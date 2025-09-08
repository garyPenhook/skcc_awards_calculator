#!/usr/bin/env python3
# pyright: reportMissingImports=false
# ruff: noqa: PLR0915, PLR0912, PLR2004, SIM102, SIM105, BLE001
# pylint: disable=broad-except, import-error, attribute-defined-outside-init,
# pylint: disable=unused-argument, too-many-lines
"""Clean QSO Form with Country/State Support."""

import asyncio
import json
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Sequence, cast

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adif_io.adif_writer import append_record  # noqa: E402
from gui._fallback_roster import _FallbackRosterManager  # noqa: E402
from gui.components.space_weather_panel import SpaceWeatherPanel  # noqa: E402,F401
from models.key_type import DISPLAY_LABELS, KeyType, normalize  # noqa: E402
from models.qso import QSO  # noqa: E402
from utils.backup_manager import backup_manager  # noqa: E402
from utils.cluster_client import ClusterSpot, SKCCClusterClient  # noqa: E402
from utils.roster_manager import RosterManager  # noqa: E402

# Decorative image handling (Pillow import now isolated in components.decor_image)

# Assets directory for decorative images
ASSETS_DIR = ROOT / "assets"
BUG_IMAGE_PRIMARY = ASSETS_DIR / "bug.png"
BUG_IMAGE_FALLBACK = ASSETS_DIR / "bug.jpg"


# Add backend services for country lookup (append so top-level models/ wins import resolution)
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.append(str(BACKEND_APP))

try:
    from services.skcc import get_dxcc_country, parse_adif  # type: ignore
except ImportError:
    # Fallback if backend services not available
    def get_dxcc_country(_call):
        return None

    def parse_adif(_content):
        return []


from gui.components.roster_progress import RosterProgressDialog  # noqa: E402


class QSOForm(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master, padding=12)
        self.pack(fill="both", expand=True)

        # QSO timing tracking
        self.qso_start_time = None  # Will be set when callsign is entered

        # Cluster client initialization
        self.cluster_client = None

        # Predeclare attributes to satisfy static analyzers
        self.adif_var = tk.StringVar()
        self.time_display_var = tk.StringVar()
        self.call_var = tk.StringVar()
        self.call_entry = None
        self.call_row = 0
        self.autocomplete_frame = None
        self.autocomplete_listbox = None
        self.previous_qso_var = tk.StringVar()
        self.previous_qso_label = None
        self.freq_var = tk.StringVar()
        self.band_var = tk.StringVar()
        self.rst_s_var = tk.StringVar()
        self.rst_r_var = tk.StringVar()
        self.pwr_var = tk.StringVar()
        self.their_skcc_var = tk.StringVar()
        self.key_var = tk.StringVar()
        self.key_combo = None
        self.country_var = tk.StringVar()
        self.state_var = tk.StringVar()
        self.roster_status_var = tk.StringVar()
        self.app_status_var = tk.StringVar()
        self.app_status_label = None
        self._bug_img = None
        # Space weather vars moved into SpaceWeatherPanel component
        # Predeclare panel widgets to avoid attribute errors before build
        # Treeview widgets (initialized later in UI build)
        self.qso_tree: ttk.Treeview | None = None
        self.spots_tree: ttk.Treeview | None = None
        self.cluster_connect_btn = None  # type: ignore[assignment]
        self.cluster_status_var = tk.StringVar(value="Disconnected")
        self.cluster_status_label = None  # type: ignore[assignment]

        # Show progress dialog during initialization
        self.progress_dialog = RosterProgressDialog(master)

        # Initialize roster manager with progress updates
        self._initialize_roster()

        # Initialize backup configuration
        self.backup_config_file = Path.home() / ".skcc_awards" / "backup_config.json"
        self.backup_config = self._load_backup_config()

        # Track whether the ADIF file has changed during this session
        self._adif_dirty = False

        self._build_widgets()
        self._update_time_display()

        # Close progress dialog
        self.progress_dialog.close()

    def __del__(self):
        """Cleanup when the form is destroyed."""
        if hasattr(self, "cluster_client") and self.cluster_client:
            self.cluster_client.disconnect()

    # ------------------------------------------------------------------
    # Right panel (Recent QSOs + RBN Spots)
    # ------------------------------------------------------------------
    def _build_right_panel(self, parent: tk.Widget) -> None:  # noqa: D401
        """Create right side panel containing recent QSO history and RBN spots."""
        # Recent QSOs
        history_frame = ttk.LabelFrame(parent, text="Recent QSOs", padding=6)
        history_frame.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self.qso_tree = ttk.Treeview(
            history_frame,
            columns=("Time", "Call", "Band", "SKCC", "Key"),
            show="headings",
            height=8,
        )
        for col, width in (
            ("Time", 70),
            ("Call", 90),
            ("Band", 60),
            ("SKCC", 90),
            ("Key", 70),
        ):
            self.qso_tree.heading(col, text=col)
            self.qso_tree.column(col, width=width, anchor="center")
        self.qso_tree.pack(fill="both", expand=True)

        # Cluster / spots
        cluster_frame = ttk.LabelFrame(parent, text="RBN Spots", padding=6)
        cluster_frame.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        # Preserve existing status var if already created
        if not isinstance(getattr(self, "cluster_status_var", None), tk.StringVar):
            self.cluster_status_var = tk.StringVar(value="Disconnected")
        status_row = ttk.Frame(cluster_frame)
        status_row.pack(fill="x")
        self.cluster_status_label = ttk.Label(
            status_row, textvariable=self.cluster_status_var, foreground="red"
        )
        self.cluster_status_label.pack(side=tk.LEFT)
        if self.cluster_connect_btn is None:
            # Initial text clarifies target network
            self.cluster_connect_btn = ttk.Button(
                status_row, text="Connect to RBN", command=self._toggle_cluster
            )
        else:
            # Ensure existing button has correct command/text after rebuild
            self.cluster_connect_btn.config(text="Connect to RBN", command=self._toggle_cluster)
        self.cluster_connect_btn.pack(side=tk.RIGHT)

        self.spots_tree = ttk.Treeview(
            cluster_frame,
            columns=(
                "Time",
                "Call",
                "SKCC",
                "Clubs",
                "Freq",
                "Band",
                "Spotter",
                "SNR",
            ),
            show="headings",
            height=10,
        )
        for col, width in (
            ("Time", 70),
            ("Call", 90),
            ("SKCC", 90),
            ("Clubs", 150),
            ("Freq", 80),
            ("Band", 60),
            ("Spotter", 90),
            ("SNR", 50),
        ):
            self.spots_tree.heading(col, text=col)
            self.spots_tree.column(col, width=width, anchor="center")
        self.spots_tree.pack(fill="both", expand=True)

        def _no_op_event(_event):  # noqa: D401
            return "break"

        self.spots_tree.bind("<Double-Button-1>", _no_op_event)

    def _initialize_roster(self):
        """Initialize roster manager with progress updates."""
        try:
            self.progress_dialog.update_status("Initializing roster manager...")
            self.roster_manager = RosterManager()

            # Get current roster status
            status = self.roster_manager.get_status()
            member_count = status.get("member_count", 0)
            last_update = status.get("last_update")
            # Retrieve but don't use; status display below is sufficient
            # (kept for potential future use)
            status.get("needs_update", False)

            if last_update:
                if isinstance(last_update, str):
                    try:
                        last_update_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
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
                f"Members: {member_count:,} | Last update: {last_update_str}",
            )

            # Check for roster updates on every startup (with 1-hour minimum interval)
            # This ensures fresh roster data while respecting server load limits
            self.progress_dialog.update_status("Checking for roster updates...")
            # Run roster update in a thread to avoid blocking UI
            self._update_roster_async()

        except Exception as e:
            self.progress_dialog.update_status(
                f"Roster initialization error: {e}",
                "Continuing without roster auto-fill",
            )
            # Create a minimal roster manager or use a dummy
            try:
                self.roster_manager = RosterManager()
            except Exception as create_rm_err:
                print(f"Warning: Could not create roster manager: {create_rm_err}")
                self.roster_manager = _FallbackRosterManager()
            # Minimal right panel builder will be available as class method (defined below)

        # ---------------- Safeguarded methods referencing optional widgets ---------

    def _add_recent_qso_row(self, time_str: str, call: str, band: str, skcc: str, key: str) -> None:
        """Insert a recent QSO row, pruning list to max 50 entries.

        The prior static type error ("Never is not iterable") came from pyright
        inferring an impossible type for the children variable due to the
        optional nature of self.qso_tree. We add explicit typing and casting to
        keep the analyzer satisfied while remaining safe at runtime.
        """
        tree = self.qso_tree
        if tree is None:
            return
        try:
            tree.insert("", 0, values=(time_str, call, band, skcc, key))
            children: Sequence[str] = cast(Sequence[str], tree.get_children())
            if len(children) > 50:
                # Convert to list for slicing certainty
                for item in list(children)[50:]:
                    tree.delete(item)
        except Exception:
            # Silently ignore any UI update issues
            pass

    def _safe_spots_insert(self, values: tuple[str, ...]):
        if not self.spots_tree:
            return
        try:
            self.spots_tree.insert("", 0, values=values)
        except Exception:
            pass

    def _update_roster_async(self):
        """Update roster in background with progress updates."""
        # Only update if we have a real roster manager
        if not hasattr(self.roster_manager, "ensure_roster_updated"):
            self.progress_dialog.update_status(
                "Roster update skipped", "No roster manager available"
            )
            try:
                self._set_status(
                    "Roster update skipped: No roster manager",
                    color="orange",
                    duration_ms=0,
                )
            except Exception:
                pass
            return

        def update_worker():
            def progress_callback(message):
                # Schedule UI update on main thread
                self.after(
                    0,
                    lambda: self.progress_dialog.update_status("Updating roster...", message),
                )

            loop = None
            try:
                # Use asyncio to run the async roster update
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                success, message = loop.run_until_complete(
                    self.roster_manager.ensure_roster_updated(
                        force=False,
                        progress_callback=progress_callback,
                        max_age_hours=1,  # Only update if older than 1 hour
                    )
                )

                if success:
                    status = self.roster_manager.get_status()
                    member_count = status.get("member_count", 0)
                    last_update = status.get("last_update")

                    # Format last update time
                    if last_update:
                        try:
                            if isinstance(last_update, str):
                                last_update_dt = datetime.fromisoformat(
                                    last_update.replace("Z", "+00:00")
                                )
                            else:
                                last_update_dt = last_update
                            last_update_str = last_update_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                        except Exception:
                            last_update_str = str(last_update)
                    else:
                        last_update_str = "Never"

                    # Schedule UI update on main thread
                    self.after(
                        0,
                        lambda: self.progress_dialog.show_final_status(
                            "Roster update completed",
                            f"Ready with {member_count:,} members | Updated: {last_update_str}",
                        ),
                    )

                    # Auto-close after showing status for a few seconds and update display
                    def close_and_update():
                        self.progress_dialog.close()
                        self._update_roster_status_display()
                        try:
                            self._set_status(
                                f"Roster updated: {member_count:,} members" f" | {last_update_str}",
                                color="green",
                                duration_ms=0,
                            )
                        except Exception:
                            pass

                    self.after(3000, close_and_update)
                else:
                    # Schedule UI update on main thread
                    self.after(
                        0,
                        lambda: self.progress_dialog.show_final_status(
                            "Roster update failed", message
                        ),
                    )
                    try:
                        self._set_status(
                            f"Roster update failed: {message}",
                            color="red",
                            duration_ms=0,
                        )
                    except Exception:
                        pass

            except Exception as e:
                # Schedule UI update on main thread
                error_msg = str(e)
                self.after(
                    0,
                    lambda: self.progress_dialog.update_status("Roster update error", error_msg),
                )
                try:
                    self._set_status(
                        f"Roster update error: {error_msg}",
                        color="red",
                        duration_ms=0,
                    )
                except Exception:
                    pass
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
                with open(self.backup_config_file, encoding="utf-8") as f:
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
        # Additional row for status bar (non-expanding)
        self.rowconfigure(1, weight=0)

        # Create main left and right frames
        left_frame = ttk.LabelFrame(self, text="QSO Entry", padding=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)

        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)

        # Configure left frame for form elements
        left_frame.columnconfigure(1, weight=1)

        # Build QSO form in left frame
        self._build_qso_form(left_frame)

        # Build right panel with QSO history and Reverse Beacon Network spots
        if hasattr(self, "_build_right_panel"):
            self._build_right_panel(right_frame)
        # Space Weather panel (bottom full width)
        try:
            self.space_weather_panel = SpaceWeatherPanel(self.master)
            self.space_weather_panel.pack(side=tk.BOTTOM, fill="x", padx=8, pady=(0, 8))
        except Exception:
            self.space_weather_panel = None

        # ------------------------------------------------------------------
        # Status bar
        # ------------------------------------------------------------------
        # Only create once; rebuilds should not duplicate
        if self.app_status_label is None:
            status_frame = ttk.Frame(self)
            status_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 4))
            # Give frame a separator style feel (optional)
            try:
                ttk.Separator(self, orient="horizontal").grid(
                    row=2, column=0, columnspan=2, sticky="ew"
                )
            except Exception:
                pass
            self.app_status_var.set("Ready")
            self.app_status_label = ttk.Label(
                status_frame,
                textvariable=self.app_status_var,
                anchor="w",
                relief="sunken",
                padding=(4, 2),
            )
            self.app_status_label.pack(fill="x")

    def _build_qso_form(self, parent):
        """Build the QSO entry form in the left panel."""
        r = 0

        # File selection
        ttk.Label(parent, text="ADIF Log File").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        file_frame = ttk.Frame(parent)
        file_frame.grid(row=r, column=1, sticky="ew", padx=6, pady=4)
        self.adif_var = tk.StringVar()
        self.adif_var.trace_add("write", self._on_adif_file_change)
        ttk.Entry(file_frame, textvariable=self.adif_var, width=40).pack(
            side=tk.LEFT, padx=(0, 6), fill="x", expand=True
        )
        ttk.Button(file_frame, text="Browse", command=self._browse_adif).pack(side=tk.RIGHT)
        r += 1

        # Time display
        ttk.Label(parent, text="QSO Time:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.time_display_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.time_display_var, foreground="green").grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        # Call with auto-complete
        ttk.Label(parent, text="Call").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.call_var = tk.StringVar()
        self.call_entry = ttk.Entry(parent, textvariable=self.call_var, width=20)
        self.call_entry.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.call_var.trace_add("write", self._on_callsign_change)
        # Remember the call row and reserve the next row for autocomplete dropdown
        self.call_row = r

        # Auto-complete listbox (initially hidden)
        self.autocomplete_frame = ttk.Frame(parent)
        self.autocomplete_listbox = tk.Listbox(self.autocomplete_frame, height=5, width=30)
        self.autocomplete_listbox.bind("<Double-Button-1>", self._select_autocomplete)

        # Previous QSO indicator (placed two rows below Call)
        prev_row = self.call_row + 2
        ttk.Label(parent, text="Previous QSO:").grid(
            row=prev_row, column=0, sticky="e", padx=6, pady=4
        )
        self.previous_qso_var = tk.StringVar()
        self.previous_qso_label = ttk.Label(
            parent,
            textvariable=self.previous_qso_var,
            foreground="orange",
            font=("Arial", 9),
            wraplength=380,
            justify="left",
        )
        self.previous_qso_label.grid(row=prev_row, column=1, sticky="w", padx=6, pady=4)
        # Track this row and continue building from the next row
        self.prev_qso_row = prev_row
        r = self.prev_qso_row + 1

        # Freq & Band
        ttk.Label(parent, text="Freq (MHz)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.freq_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.freq_var, width=10).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        ttk.Label(parent, text="Band (e.g. 40M)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.band_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.band_var, width=10).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        # Reports
        ttk.Label(parent, text="RST sent").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.rst_s_var = tk.StringVar(value="599")
        ttk.Entry(parent, textvariable=self.rst_s_var, width=6).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        ttk.Label(parent, text="RST rcvd").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.rst_r_var = tk.StringVar(value="599")
        ttk.Entry(parent, textvariable=self.rst_r_var, width=6).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        # Power
        ttk.Label(parent, text="Power (W)").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.pwr_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.pwr_var, width=6).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        # SKCC numbers
        ttk.Label(parent, text="Their SKCC #").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.their_skcc_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.their_skcc_var, width=12).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        # Country (auto-filled from callsign)
        ttk.Label(parent, text="Country").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.country_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.country_var, width=20).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        # State (manual entry for US stations)
        ttk.Label(parent, text="State/Province").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.state_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.state_var, width=8).grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1

        # Key used (REQUIRED for Triple Key)
        ttk.Label(parent, text="Key used").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.key_var = tk.StringVar()
        options = [
            DISPLAY_LABELS[KeyType.STRAIGHT],
            DISPLAY_LABELS[KeyType.BUG],
            DISPLAY_LABELS[KeyType.SIDESWIPER],
        ]
        self.key_combo = ttk.Combobox(
            parent,
            textvariable=self.key_var,
            values=options,
            state="readonly",
            width=20,
        )
        self.key_combo.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.key_combo.current(0)
        r += 1

        # Buttons
        btn_row = ttk.Frame(parent)
        btn_row.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_row, text="Save QSO", command=self._save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Backup Config", command=self._configure_backup).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(btn_row, text="Backup now", command=self._backup_now).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Quit", command=self._quit).pack(side=tk.LEFT, padx=6)
        r += 1

        # Roster status display
        ttk.Label(parent, text="Roster Status:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.roster_status_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.roster_status_var, width=45, anchor="w").grid(
            row=r, column=1, sticky="w", padx=6, pady=4
        )
        r += 1
        # (Space weather UI removed; handled by SpaceWeatherPanel component)

    def _update_roster_status_display(self):
        """Update the roster status display in the main form."""
        try:
            if hasattr(self.roster_manager, "get_status"):
                status = self.roster_manager.get_status()
                member_count = status.get("member_count", 0)
                last_update = status.get("last_update")

                if last_update:
                    try:
                        if isinstance(last_update, str):
                            last_update_dt = datetime.fromisoformat(
                                last_update.replace("Z", "+00:00")
                            )
                        else:
                            last_update_dt = last_update
                        last_update_str = last_update_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except Exception:
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
            filetypes=[("ADIF files", "*.adif *.adi"), ("All files", "*.*")],
        )
        if file_path:
            self.adif_var.set(file_path)
            # Load and display recent QSOs from the file
            self._load_recent_qsos(file_path)
            # Status: selected ADIF file
            try:
                self._set_status(
                    f"Selected ADIF: {Path(file_path).name}",
                    color="blue",
                    duration_ms=0,
                )
            except Exception:
                pass

    def _update_time_display(self):
        try:
            now = datetime.now()
            utc_now = now.astimezone(timezone.utc)

            if self.qso_start_time:
                # QSO in progress - show duration
                duration = utc_now - self.qso_start_time
                duration_minutes = int(duration.total_seconds() / 60)
                duration_seconds = int(duration.total_seconds() % 60)

                display_time = (
                    f"QSO in progress: {duration_minutes:02d}:{duration_seconds:02d} "
                    f"(Started: {self.qso_start_time.strftime('%H:%M:%S UTC')})"
                )
                self.time_display_var.set(display_time)
            else:
                # No QSO in progress - show current time
                display_time = (
                    f"{now.strftime('%H:%M:%S')} local ({utc_now.strftime('%H:%M:%S')} UTC)"
                )
                self.time_display_var.set(display_time)

            self.after(1000, self._update_time_display)
        except Exception as e:
            print(f"Time display error: {e}")
            self.after(5000, self._update_time_display)

    def _on_callsign_change(self, *_args):
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

            # Check for previous QSOs with this callsign
            self._check_previous_qso(callsign)
        else:
            # Clear previous QSO info when callsign is cleared
            self.previous_qso_var.set("")

        if len(callsign) >= 2:  # Start suggesting after 2 characters
            try:
                # Search for matching callsigns
                matches = self.roster_manager.search_callsigns(callsign, limit=10)

                # Check for exact match and auto-fill SKCC number and state
                exact_match = None
                for match in matches:
                    if match["call"].upper() == callsign.upper():
                        exact_match = match
                        break

                if exact_match:
                    # Auto-fill SKCC number for exact match
                    if not self.their_skcc_var.get():
                        self.their_skcc_var.set(exact_match["number"])

                    # Auto-fill state for exact match (only if currently empty)
                    if not self.state_var.get() and exact_match.get("state"):
                        self.state_var.set(exact_match["state"])

                # Also try direct member lookup for more complete information
                try:
                    member_info = self.roster_manager.lookup_member(callsign)
                    if member_info:
                        if not self.their_skcc_var.get():
                            self.their_skcc_var.set(member_info["number"])
                        if not self.state_var.get() and member_info.get("state"):
                            self.state_var.set(member_info["state"])
                except Exception as e:
                    print(f"Member lookup error: {e}")

                if matches:
                    # Show autocomplete listbox
                    self.autocomplete_listbox.delete(0, tk.END)
                    for match in matches:
                        display_text = f"{match['call']} - SKCC #{match['number']}"
                        self.autocomplete_listbox.insert(tk.END, display_text)

                    # Position the autocomplete listbox in the reserved row beneath Call
                    self.autocomplete_frame.grid(
                        row=self.call_row + 1,
                        column=1,
                        sticky="w",
                        padx=6,
                        pady=2,
                    )
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

    def _on_adif_file_change(self, *_args):
        """Handle ADIF file path changes to reload recent QSOs."""
        file_path = self.adif_var.get().strip()
        if file_path and Path(file_path).exists():
            # New file selected; assume clean state until the next save
            self._adif_dirty = False
            self._load_recent_qsos(file_path)

    def _select_autocomplete(self, _event=None):
        """Handle selection from autocomplete listbox."""
        try:
            selection = self.autocomplete_listbox.get(self.autocomplete_listbox.curselection())
            if selection:
                # Extract callsign from "CALL - SKCC #NUMBER" format
                call = selection.split(" - ")[0]
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
                when=start_utc,  # QSO start time (when callsign was entered)
                time_off=utc_end_time,  # QSO end time (when Save was pressed)
                freq_mhz=self._parse_float(self.freq_var.get()),
                band=(self.band_var.get().strip().upper() or None),
                rst_s=(self.rst_s_var.get().strip() or None),
                rst_r=(self.rst_r_var.get().strip() or None),
                tx_pwr_w=(
                    self._parse_float(self.pwr_var.get()) if self.pwr_var.get().strip() else None
                ),
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

            # Backup is now performed on application exit, not after each save

            # Mark ADIF as changed so a backup will run on exit
            self._adif_dirty = True

            # Add the QSO to the recent QSOs view
            self._add_qso_to_view(q)

            # Enhanced save message with duration info
            duration_text = (
                f"Duration: {duration_minutes:02d}:{duration_seconds:02d}"
                if duration_minutes > 0 or duration_seconds > 0
                else "Duration: <1 sec"
            )
            messagebox.showinfo(
                "Saved",
                f"QSO with {q.call} saved to ADIF file.\n"
                f"{duration_text}\n"
                f"Country: {q.country}\n"
                f"State: {q.state}\n"
                f"Start: {start_utc.strftime('%H:%M:%S UTC')}\n"
                f"End: {utc_end_time.strftime('%H:%M:%S UTC')}",
            )

            # Also reflect save in status line (persistent)
            summary = f"Saved QSO {q.call}" f" | {q.band or ''}" f" | {duration_text}"
            self._set_status(summary, color="green", duration_ms=0)

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
                "sideswiper": "Sideswiper",
            }
            key = key_display.get(qso.my_key.value.lower() if qso.my_key else "", "")

            # Insert at the top of the list
            self.qso_tree.insert("", 0, values=(time_str, call, band, skcc, key))

            # Remove oldest entries to keep only 15
            children = self.qso_tree.get_children()
            if len(children) > 15:
                for item in children[15:]:
                    self.qso_tree.delete(item)

        except Exception as e:
            print(f"Error adding QSO to view: {e}")

    def _load_recent_qsos(self, file_path):
        """Load and display recent QSOs from the selected ADIF file."""
        try:
            # Clear existing QSO tree
            for item in self.qso_tree.get_children():
                self.qso_tree.delete(item)

            # Read ADIF file
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Parse ADIF content
            qsos = parse_adif(content)

            if not qsos:
                print(f"No QSOs found in {file_path}")
                return

            # Sort QSOs by date/time (most recent first)
            def qso_datetime_key(qso):
                try:
                    if qso.date and qso.time_on:
                        # Combine date and time
                        date_str = qso.date  # YYYYMMDD
                        time_str = qso.time_on.ljust(6, "0")  # Pad time to HHMMSS
                        datetime_str = f"{date_str}{time_str}"
                        return datetime.strptime(datetime_str, "%Y%m%d%H%M%S")
                    elif qso.date:
                        # Date only
                        return datetime.strptime(qso.date, "%Y%m%d")
                    else:
                        # No date, put at the end
                        return datetime.min
                except (ValueError, TypeError):
                    return datetime.min

            sorted_qsos = sorted(qsos, key=qso_datetime_key, reverse=True)

            # Display the most recent 20 QSOs
            for qso in sorted_qsos[:20]:
                try:
                    # Format time display
                    if qso.date and qso.time_on:
                        # Parse date and time
                        date_obj = datetime.strptime(qso.date, "%Y%m%d")
                        if len(qso.time_on) >= 4:
                            time_str = qso.time_on.ljust(6, "0")  # Pad to HHMMSS
                            hour = int(time_str[:2])
                            minute = int(time_str[2:4])
                            time_display = f"{date_obj.strftime('%m/%d')} {hour:02d}:{minute:02d}"
                        else:
                            time_display = date_obj.strftime("%m/%d")
                    elif qso.date:
                        date_obj = datetime.strptime(qso.date, "%Y%m%d")
                        time_display = date_obj.strftime("%m/%d")
                    else:
                        time_display = ""

                    call = qso.call or ""
                    band = qso.band or ""
                    skcc = qso.skcc or ""

                    # Format key type
                    key_display = ""
                    if qso.key_type:
                        key_lower = qso.key_type.lower()
                        if "straight" in key_lower or key_lower == "sk":
                            key_display = "Straight"
                        elif "bug" in key_lower or "semi" in key_lower:
                            key_display = "Bug"
                        elif "side" in key_lower or "cootie" in key_lower or key_lower == "ss":
                            key_display = "Sideswiper"
                        else:
                            key_display = qso.key_type.title()

                    # Insert into tree
                    self.qso_tree.insert(
                        "", "end", values=(time_display, call, band, skcc, key_display)
                    )

                except Exception as e:
                    print(f"Error processing QSO {qso.call}: {e}")
                    continue

            loaded_count = min(len(sorted_qsos), 20)
            print(f"Loaded {loaded_count} recent QSOs from {file_path}")
            try:
                self._set_status(
                    f"Loaded {loaded_count} recent QSOs from {Path(file_path).name}",
                    color="blue",
                    duration_ms=0,
                )
            except Exception:
                pass

        except FileNotFoundError:
            print(f"ADIF file not found: {file_path}")
        except Exception as e:
            print(f"Error loading QSOs from {file_path}: {e}")

    def _check_previous_qso(self, callsign):
        """Check if this callsign has been worked before in the current ADIF file."""
        file_path = self.adif_var.get().strip()
        if not file_path or not Path(file_path).exists():
            self.previous_qso_var.set("")
            return

        try:
            # Read and parse ADIF file
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            qsos = parse_adif(content)

            # Look for previous QSOs with this callsign
            previous_qsos = []
            for qso in qsos:
                if qso.call and qso.call.upper() == callsign.upper():
                    previous_qsos.append(qso)

            if not previous_qsos:
                self.previous_qso_var.set("New contact")
                self.previous_qso_label.config(foreground="green")
                return

            # Sort by date to find the most recent previous QSO
            def qso_datetime_key(qso):
                try:
                    if qso.date and qso.time_on:
                        date_str = qso.date
                        time_str = qso.time_on.ljust(6, "0")
                        datetime_str = f"{date_str}{time_str}"
                        return datetime.strptime(datetime_str, "%Y%m%d%H%M%S")
                    elif qso.date:
                        return datetime.strptime(qso.date, "%Y%m%d")
                    else:
                        return datetime.min
                except (ValueError, TypeError):
                    return datetime.min

            sorted_previous = sorted(previous_qsos, key=qso_datetime_key, reverse=True)
            most_recent = sorted_previous[0]

            # Format the previous QSO information
            prev_info = f"Worked {len(previous_qsos)} time{'s' if len(previous_qsos) > 1 else ''}"

            if most_recent.date:
                try:
                    date_obj = datetime.strptime(most_recent.date, "%Y%m%d")
                    prev_info += f" | Last: {date_obj.strftime('%m/%d/%Y')}"
                except ValueError:
                    prev_info += f" | Last: {most_recent.date}"

            if most_recent.skcc:
                prev_info += f" | SKCC: {most_recent.skcc}"

            if most_recent.band:
                prev_info += f" | {most_recent.band}"

            self.previous_qso_var.set(prev_info)

            # Color code based on number of previous contacts
            if len(previous_qsos) == 1:
                self.previous_qso_label.config(foreground="orange")  # Duplicate
            else:
                self.previous_qso_label.config(foreground="red")  # Multiple contacts

        except Exception as e:
            print(f"Error checking previous QSOs for {callsign}: {e}")
            self.previous_qso_var.set("")

    def _quit(self):
        """Gracefully close the app and create a backup on exit."""
        try:
            adif_path = getattr(self, "adif_var", None)
            file_path = adif_path.get().strip() if adif_path else ""
            if self._adif_dirty and file_path:
                # Create backup silently on exit (no popups)
                _ = backup_manager.create_backup(file_path)
        except Exception as e:
            print(f"Backup on exit failed: {e}")
        finally:
            self.winfo_toplevel().destroy()

    # Public wrapper to avoid accessing a protected member from outside
    def close(self):
        self._quit()

    def _backup_now(self):
        """Create a backup immediately for the selected ADIF file (status only)."""
        try:
            file_path = self.adif_var.get().strip()
            if not file_path:
                self._set_status(
                    "No ADIF file selected for backup.",
                    color="orange",
                    duration_ms=0,
                )
                return
            success = backup_manager.create_backup(file_path)
            if success:
                self._set_status(
                    f"Backup created: {Path(file_path).name}",
                    color="green",
                    duration_ms=0,
                )
            else:
                self._set_status(
                    "Backup failed. Check settings and path.",
                    color="red",
                    duration_ms=0,
                )
        except Exception as e:
            self._set_status(f"Backup failed: {e}", color="red", duration_ms=0)

    def _set_status(self, message: str, color: str = "gray", duration_ms: int = 0) -> None:
        """Show a status message with a clock-style timestamp.

        If duration_ms <= 0, it persists.
        """
        try:
            self.app_status_label.configure(foreground=color)
            ts = datetime.now().strftime("%H:%M:%S")
            self.app_status_var.set(f"🕒 {ts} — {message}")
            if duration_ms and duration_ms > 0:
                self.after(duration_ms, lambda: self.app_status_var.set(""))
        except Exception as e:
            print(f"Status update error: {e}")

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
        ttk.Checkbutton(
            main_frame,
            text="Enable automatic backups on exit",
            variable=backup_enabled_var,
        ).pack(anchor="w", pady=5)

        # Backup folder
        ttk.Label(main_frame, text="Backup folder:").pack(anchor="w", pady=(10, 2))

        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill="x", pady=2)

        backup_folder_var = tk.StringVar(value=self.backup_config.get("backup_folder", ""))
        ttk.Entry(folder_frame, textvariable=backup_folder_var, width=50).pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )
        ttk.Button(
            folder_frame,
            text="Browse",
            command=lambda: self._browse_folder(backup_folder_var),
        ).pack(side="right")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)

        def save_config():
            self.backup_config["backup_enabled"] = backup_enabled_var.get()
            self.backup_config["backup_folder"] = backup_folder_var.get()

            # Save to file
            self.backup_config_file.parent.mkdir(exist_ok=True)
            with open(self.backup_config_file, "w", encoding="utf-8") as f:
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
        """Toggle RBN connection on/off."""
        if self.cluster_client and self.cluster_client.connected:
            # Disconnect
            self.cluster_client.disconnect()
            self.cluster_client = None
            self.cluster_connect_btn.config(text="Connect to RBN")
            self.cluster_status_var.set("Disconnected")
            self.cluster_status_label.config(foreground="red")
            try:
                self._set_status("RBN disconnected", color="orange", duration_ms=0)
            except Exception:
                pass
        else:
            # Connect - prompt for callsign
            callsign = self._get_cluster_callsign()
            if not callsign:
                return

            self.cluster_client = SKCCClusterClient(
                callsign,
                self._on_new_spot,
                include_clubs=None,  # None => request all club annotations
            )

            if self.cluster_client.connect():
                self.cluster_connect_btn.config(text="Disconnect")
                self.cluster_status_var.set(f"Connected as {callsign}")
                self.cluster_status_label.config(foreground="green")
                try:
                    self._set_status(
                        f"RBN connected as {callsign}",
                        color="green",
                        duration_ms=0,
                    )
                except Exception:
                    pass
            else:
                self.cluster_client = None
                self.cluster_status_var.set("Connection failed")
                self.cluster_status_label.config(foreground="red")
                try:
                    self._set_status(
                        "RBN connection failed",
                        color="red",
                        duration_ms=0,
                    )
                except Exception:
                    pass

    def _on_new_spot(self, spot: ClusterSpot):
        """Handle new RBN spot."""
        # Use after() to safely update GUI from background thread
        self.after(0, self._add_spot_to_tree, spot)

    def _add_spot_to_tree(self, spot: ClusterSpot):
        """Add a new RBN spot to the spots treeview (thread-safe)."""
        try:
            # Format values for display
            time_str = spot.time_utc.strftime("%H:%M")
            freq_str = f"{spot.frequency:.3f}"  # Show 3 decimal places for accuracy
            snr_str = f"{spot.snr}dB" if spot.snr else ""

            # Check for existing spots from the same callsign and remove them
            duplicate_found = False
            children = self.spots_tree.get_children()
            for child in children:
                values = self.spots_tree.item(child, "values")
                if values and len(values) > 2 and values[1] == spot.callsign:
                    # Found duplicate callsign - remove the older spot
                    old_freq = values[4] if len(values) > 4 else "unknown"
                    print(
                        "Duplicate filter: Replacing "
                        f"{spot.callsign} {old_freq} MHz with {freq_str} MHz"
                    )
                    self.spots_tree.delete(child)
                    duplicate_found = True

            # Lookup SKCC membership number for the spotted callsign
            skcc_display = ""
            try:
                info = self.roster_manager.lookup_member(spot.callsign)
                if info and info.get("number"):
                    skcc_display = info["number"]
            except Exception:
                skcc_display = ""

            # Clubs from the spot feed (e.g., CWOPS, A1A, FISTS)
            clubs_display = getattr(spot, "clubs", None) or ""

            # Merge/deduplicate: keep existing clubs and ensure SKCC is added when member.
            try:
                clubs_set = set(c.strip().upper() for c in clubs_display.split(",") if c.strip())
                if skcc_display:
                    clubs_set.add("SKCC")
                # Display in a stable order with SKCC first if present
                ordered = [
                    *(["SKCC"] if "SKCC" in clubs_set else []),
                    *sorted(x for x in clubs_set if x != "SKCC"),
                ]
                clubs_display = ", ".join(ordered)
            except Exception:
                pass

            # Insert new spot at the top of the tree
            item = self.spots_tree.insert(
                "",
                0,
                values=(
                    time_str,
                    spot.callsign,
                    skcc_display,
                    clubs_display,
                    freq_str,
                    spot.band,
                    spot.spotter,
                    snr_str,
                ),
            )

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

    def _on_spot_double_click(self, _event):
        """Handle double-click on an RBN spot to auto-fill frequency."""
        try:
            item = self.spots_tree.selection()[0]
            values = self.spots_tree.item(item, "values")

            if values:
                callsign = values[1]
                frequency = values[4]
                band = values[5]

                # Auto-fill the form
                self.call_var.set(callsign)
                self.freq_var.set(frequency)
                self.band_var.set(band)

                # Focus on the call entry to trigger any auto-fill logic
                self.call_entry.focus_set()

                print(f"Auto-filled from spot: {callsign} on {frequency} MHz ({band})")
                try:
                    self._set_status(
                        f"From spot: {callsign} @ {frequency} MHz ({band})",
                        color="blue",
                        duration_ms=0,
                    )
                except Exception:
                    pass

        except (IndexError, Exception) as e:
            print(f"Error handling spot double-click: {e}")

    def _get_cluster_callsign(self) -> Optional[str]:
        """Prompt user for RBN callsign."""
        from tkinter import simpledialog

        callsign = simpledialog.askstring(
            "RBN Connection",
            (
                "Enter your callsign (you may append -SKCC / -TEST etc.; "
                "leave suffix off for plain call):"
            ),
        )

        if callsign:
            return callsign.upper().strip()
        return None


def main():
    root = tk.Tk()
    root.title("W4GNS SKCC Logger - Reverse Beacon Network spots")
    root.geometry("1200x700")  # Wider layout for two-column design
    root.minsize(1000, 600)  # Minimum size to see all features

    app = QSOForm(root)
    # Ensure backups run when the user closes the window via the titlebar (X)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
