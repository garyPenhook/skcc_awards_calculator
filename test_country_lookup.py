#!/usr/bin/env python3
"""Test script for country lookup in QSO logger."""

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
from services.skcc import get_dxcc_country

def test_country_lookup():
    """Test the country lookup and QSO creation with state/country fields."""
    
    # Test callsigns
    test_calls = [
        'W1AW',      # United States
        'VE1ABC',    # Canada  
        'G0ABC',     # England
        'JA1ABC',    # Japan
        'DL1ABC',    # Germany
    ]
    
    print("Testing country lookup:")
    for call in test_calls:
        country = get_dxcc_country(call)
        print(f"  {call}: {country}")
    
    print("\nTesting QSO creation with country/state:")
    
    # Create a test QSO with country and state
    qso = QSO(
        call="W1AW",
        when=datetime.now(timezone.utc),
        mode="CW",
        freq_mhz=14.050,
        band="20M",
        rst_s="599",
        rst_r="599",
        their_skcc="1234",
        my_key=KeyType.STRAIGHT,
        country="United States",
        state="CT"
    )
    
    print(f"\nCreated QSO: {qso.call}")
    print(f"Country: {qso.country}")
    print(f"State: {qso.state}")
    
    # Test ADIF output
    fields = qso.to_adif_fields()
    print(f"\nADIF fields:")
    for tag, value in fields:
        if tag in ['CALL', 'COUNTRY', 'STATE', 'SIG', 'SIG_INFO']:
            print(f"  {tag}: {value}")

if __name__ == "__main__":
    test_country_lookup()
