#!/usr/bin/env python3
"""Test frequency display in cluster spots."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from utils.cluster_client import ClusterSpot
from datetime import datetime, timezone
import re

def test_frequency_parsing():
    """Test frequency parsing from actual RBN lines."""
    print("Testing frequency parsing from RBN lines...")
    
    # RBN spot parsing regex (same as in cluster_client.py)
    spot_pattern = re.compile(r'DX de (\S+):\s+(\d+\.\d+)\s+(\S+)\s+.*?(\d{4})Z')
    
    # Test with various frequency formats from actual RBN data
    test_lines = [
        'DX de OH6BG-#:      7026.0  W4GNS          CQ      1322Z',  # 40m
        'DX de EA2RCF-#:    14052.5  DL6ABC         CQ      1323Z',  # 20m
        'DX de DK3UA-#:     21025.0  G4XYZ          CQ      1324Z',  # 15m
        'DX de IT9GSF-#:    28030.0  JA1TEST        CQ      1325Z',  # 10m
        'DX de S50U-#:      18084.6  ON7PQ          CQ      1326Z',  # 17m
    ]
    
    for line in test_lines:
        match = spot_pattern.match(line)
        if match:
            spotter = match.group(1)
            frequency_khz = float(match.group(2))
            callsign = match.group(3)
            time_str = match.group(4)
            
            # Convert to MHz (same as cluster_client.py)
            frequency_mhz = frequency_khz / 1000.0
            
            # Create spot object
            now = datetime.now(timezone.utc)
            spot = ClusterSpot(
                callsign=callsign,
                frequency=frequency_mhz,
                spotter=spotter,
                time_utc=now
            )
            
            # Test display formatting (same as GUI)
            freq_display = f"{spot.frequency:.1f}"
            
            print(f"Line: {line}")
            print(f"  Raw kHz: {frequency_khz}")
            print(f"  MHz: {frequency_mhz:.3f}")
            print(f"  Display: {freq_display}")
            print(f"  Band: {spot.band}")
            print(f"  Callsign: {callsign}")
            print()
        else:
            print(f"No match: {line}")

if __name__ == "__main__":
    test_frequency_parsing()
