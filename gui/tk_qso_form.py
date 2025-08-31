import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timezone
import sys
from pathlib import Path

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.key_type import KeyType, DISPLAY_LABELS, normalize
from models.qso import QSO
from adif_io.adif_writer import append_record
from utils.theme_manager import theme_manager

class QSOForm(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master, padding=12)
        self.grid(sticky="nsew")
        
        # Apply theme to the parent window
        if master:
            theme_manager.apply_theme(master)
            
        self._build_ui()

    def _build_ui(self):
        r = 0
        # ADIF path
        ttk.Label(self, text="ADIF file").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.adif_var = tk.StringVar()
        adif_entry = ttk.Entry(self, textvariable=self.adif_var, width=50)
        adif_entry.grid(row=r, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(self, text="Browse…", command=self._choose_adif).grid(row=r, column=2, padx=6, pady=4)
        r += 1

        # Call
        ttk.Label(self, text="Call").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.call_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.call_var, width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4)
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

        ttk.Label(self, text="My SKCC #").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        self.my_skcc_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.my_skcc_var, width=12).grid(row=r, column=1, sticky="w", padx=6, pady=4)
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
        
        # Theme toggle button
        current_theme = "🌙" if theme_manager.current_theme == "light" else "☀️"
        self.theme_button = ttk.Button(btn_row, text=current_theme, width=3, command=self._toggle_theme)
        self.theme_button.grid(row=0, column=1, padx=6)
        
        ttk.Button(btn_row, text="Quit", command=self._quit).grid(row=0, column=2, padx=6)

        # Resize behavior
        for c in range(3):
            self.columnconfigure(c, weight=1)

    def _choose_adif(self):
        path = filedialog.asksaveasfilename(
            title="Select ADIF file",
            defaultextension=".adi",
            filetypes=[("ADIF files", "*.adi"), ("All files", "*.*")],
        )
        if path:
            self.adif_var.set(path)

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
            q = QSO(
                call=self.call_var.get().strip().upper(),
                when=datetime.now(timezone.utc),   # always UTC now
                freq_mhz=self._parse_float(self.freq_var.get()),
                band=(self.band_var.get().strip().upper() or None),
                rst_s=(self.rst_s_var.get().strip() or None),
                rst_r=(self.rst_r_var.get().strip() or None),
                station_callsign=(self.station_var.get().strip().upper() or None),
                operator=(self.op_var.get().strip().upper() or None),
                tx_pwr_w=(self._parse_float(self.pwr_var.get()) if self.pwr_var.get().strip() else None),
                their_skcc=(self.their_skcc_var.get().strip().upper() or None),
                my_skcc=(self.my_skcc_var.get().strip().upper() or None),
                my_key=normalize(self.key_var.get()),
            )
            fields = q.to_adif_fields()
            append_record(self.adif_var.get(), fields)
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
        # keep my_skcc, station, op, pwr, and key selection as convenience

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

def main():
    root = tk.Tk()
    root.title("SKCC QSO Logger")
    # tk scaling & theming are optional; keep it simple
    frm = QSOForm(root)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    root.mainloop()

if __name__ == "__main__":
    main()
