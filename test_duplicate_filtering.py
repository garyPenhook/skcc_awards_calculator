#!/usr/bin/env python3
"""Test duplicate callsign filtering in cluster spots."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from utils.cluster_client import ClusterSpot
from datetime import datetime, timezone
import time

def test_duplicate_filtering():
    """Test that duplicate callsigns are filtered correctly."""
    print("Testing duplicate callsign filtering...")
    
    # Create test spots with duplicate callsigns
    now = datetime.now(timezone.utc)
    
    test_spots = [
        # First W1TEST spot
        ClusterSpot(
            callsign="W1TEST",
            frequency=14.025,
            spotter="EA2RCF-#",
            time_utc=now
        ),
        # Different callsign
        ClusterSpot(
            callsign="DL6ABC",
            frequency=21.025,
            spotter="OH4KA-#",
            time_utc=now
        ),
        # Duplicate W1TEST (should replace first one)
        ClusterSpot(
            callsign="W1TEST",
            frequency=14.052,  # Different frequency
            spotter="DK3UA-#",  # Different spotter
            time_utc=now
        ),
        # Another different callsign
        ClusterSpot(
            callsign="G4XYZ",
            frequency=7.026,
            spotter="IT9GSF-#",
            time_utc=now
        ),
        # Another duplicate W1TEST (should replace second one)
        ClusterSpot(
            callsign="W1TEST",
            frequency=28.030,  # Yet another frequency
            spotter="S50U-#",   # Yet another spotter
            time_utc=now
        )
    ]
    
    print("Test spots created:")
    for i, spot in enumerate(test_spots, 1):
        print(f"  {i}. {spot.callsign} {spot.frequency:.3f} MHz spotted by {spot.spotter}")
    
    print("\nExpected behavior:")
    print("  - Only one W1TEST should remain (the last one: 28.030 MHz by S50U-#)")
    print("  - DL6ABC and G4XYZ should remain")
    print("  - Total spots in tree should be 3 (not 5)")
    
    print("\nTo test this manually:")
    print("  1. Run the W4GNS SKCC Logger")
    print("  2. Connect to cluster spots")
    print("  3. Watch for duplicate callsigns - only the most recent should show")
    print("  4. Each callsign should appear only once in the list")

if __name__ == "__main__":
    test_duplicate_filtering()
