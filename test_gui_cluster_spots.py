#!/usr/bin/env python3
"""Test cluster spots visibility in GUI."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

import tkinter as tk
from gui.tk_qso_form_clean import QSOForm

def test_cluster_spots_gui():
    """Test if cluster spots section is visible in GUI."""
    print("Testing cluster spots in GUI...")
    
    # Create root window
    root = tk.Tk()
    root.title("SKCC Logger - Cluster Spots Test")
    
    # Create QSO form
    qso_form = QSOForm(root)
    qso_form.pack(fill="both", expand=True)
    
    # Check if cluster spots components exist
    components_found = []
    
    if hasattr(qso_form, 'cluster_connect_btn'):
        components_found.append("✓ Connect button found")
    else:
        components_found.append("✗ Connect button NOT found")
        
    if hasattr(qso_form, 'cluster_status_var'):
        components_found.append("✓ Status variable found")
    else:
        components_found.append("✗ Status variable NOT found")
        
    if hasattr(qso_form, 'spots_tree'):
        components_found.append("✓ Spots treeview found")
    else:
        components_found.append("✗ Spots treeview NOT found")
    
    # Print results
    print("\nCluster Spots Components Check:")
    for component in components_found:
        print(f"  {component}")
    
    # Set window size to ensure everything is visible
    root.geometry("800x900")
    
    print("\nGUI created. Check for 'SKCC Cluster Spots' section at the bottom.")
    print("Look for:")
    print("  - 'SKCC Cluster Spots:' label")
    print("  - 'Connect to Cluster' button")
    print("  - Status display")
    print("  - Empty spots table with columns: Time UTC, Call, Freq, Band, Spotter, SNR")
    print("\nPress Ctrl+C to close...")
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Test completed.")
        root.destroy()

if __name__ == "__main__":
    test_cluster_spots_gui()
