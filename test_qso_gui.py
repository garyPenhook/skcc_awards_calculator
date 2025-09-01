#!/usr/bin/env python3
"""Simple test for QSO logger GUI with country/state functionality."""

import tkinter as tk
from tkinter import ttk
import sys
from pathlib import Path

# Add paths
ROOT = Path(__file__).resolve().parent
BACKEND_APP = ROOT / "backend" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

from models.qso import QSO
from models.key_type import KeyType
from datetime import datetime, timezone

try:
    from services.skcc import get_dxcc_country
except ImportError:
    def get_dxcc_country(call):
        return None

class SimpleQSOTest(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.create_widgets()
    
    def create_widgets(self):
        row = 0
        
        # Call field
        ttk.Label(self, text="Callsign:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.call_var = tk.StringVar()
        self.call_entry = ttk.Entry(self, textvariable=self.call_var, width=15)
        self.call_entry.grid(row=row, column=1, sticky="w", padx=5, pady=3)
        self.call_var.trace_add('write', self.on_callsign_change)
        row += 1
        
        # Country field (auto-filled)
        ttk.Label(self, text="Country:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.country_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.country_var, width=20).grid(row=row, column=1, sticky="w", padx=5, pady=3)
        row += 1
        
        # State field
        ttk.Label(self, text="State:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.state_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.state_var, width=10).grid(row=row, column=1, sticky="w", padx=5, pady=3)
        row += 1
        
        # Test button
        ttk.Button(self, text="Test QSO Creation", command=self.test_qso).grid(row=row, column=0, columnspan=2, pady=10)
        row += 1
        
        # Output area
        self.output_text = tk.Text(self, height=10, width=50)
        self.output_text.grid(row=row, column=0, columnspan=2, pady=5)
    
    def on_callsign_change(self, *args):
        """Handle callsign changes and auto-fill country."""
        callsign = self.call_var.get().upper().strip()
        
        if callsign:
            try:
                country = get_dxcc_country(callsign)
                if country:
                    self.country_var.set(country)
                    self.output_text.insert(tk.END, f"Auto-filled country: {callsign} -> {country}\n")
                    self.output_text.see(tk.END)
                else:
                    self.country_var.set("")
            except Exception as e:
                self.output_text.insert(tk.END, f"Country lookup error: {e}\n")
                self.output_text.see(tk.END)
    
    def test_qso(self):
        """Test QSO creation with country/state."""
        try:
            call = self.call_var.get().strip().upper()
            country = self.country_var.get().strip()
            state = self.state_var.get().strip().upper()
            
            if not call:
                self.output_text.insert(tk.END, "Error: Enter a callsign\n")
                return
            
            # Create test QSO
            qso = QSO(
                call=call,
                when=datetime.now(timezone.utc),
                mode="CW",
                my_key=KeyType.STRAIGHT,
                country=country or None,
                state=state or None
            )
            
            # Show ADIF fields
            fields = qso.to_adif_fields()
            self.output_text.insert(tk.END, f"\n--- QSO for {call} ---\n")
            
            for tag, value in fields:
                if tag in ['CALL', 'COUNTRY', 'STATE', 'MY_MORSE_KEY_TYPE']:
                    self.output_text.insert(tk.END, f"{tag}: {value}\n")
            
            self.output_text.insert(tk.END, "QSO created successfully!\n\n")
            self.output_text.see(tk.END)
            
        except Exception as e:
            self.output_text.insert(tk.END, f"Error creating QSO: {e}\n")
            self.output_text.see(tk.END)

def main():
    root = tk.Tk()
    root.title("QSO Country/State Test")
    root.geometry("600x400")
    
    app = SimpleQSOTest(root)
    
    # Add some test instructions
    app.output_text.insert(tk.END, "Test Instructions:\n")
    app.output_text.insert(tk.END, "1. Enter a callsign (e.g., W1AW, VE1ABC, G0ABC)\n")
    app.output_text.insert(tk.END, "2. Country should auto-fill\n")  
    app.output_text.insert(tk.END, "3. Enter state if applicable\n")
    app.output_text.insert(tk.END, "4. Click 'Test QSO Creation' to see ADIF output\n\n")
    
    root.mainloop()

if __name__ == "__main__":
    main()
