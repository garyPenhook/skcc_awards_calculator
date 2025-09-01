#!/usr/bin/env python3
"""Test script to verify roster update frequency."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.roster_manager import RosterManager

def test_update_frequency():
    """Test the roster update frequency logic."""
    print("Testing Roster Update Frequency")
    print("=" * 40)
    
    rm = RosterManager()
    
    # Get current status
    status = rm.get_status()
    print(f"Current status:")
    print(f"  Members: {status['member_count']:,}")
    print(f"  Last update: {status['last_update'] or 'Never'}")
    print(f"  Needs update: {status['needs_update']}")
    print()
    
    # Test the needs_update logic with different intervals
    last_update = rm.db.get_last_update()
    if last_update:
        age = datetime.now() - last_update
        print(f"Roster age: {age}")
        print(f"Age in hours: {age.total_seconds() / 3600:.2f}")
        print()
        
        print("Update checks with different intervals:")
        for hours in [1, 4, 12, 24]:
            needs_update = rm.db.needs_update(max_age_hours=hours)
            print(f"  {hours:2d} hours: {'UPDATE NEEDED' if needs_update else 'Current'}")
    else:
        print("No previous update found - roster needs initialization")
    
    print()
    print("The GUI now checks for updates on EVERY startup")
    print("but only updates if roster is older than 1 hour.")
    print("This balances frequent updates with server efficiency.")

if __name__ == "__main__":
    test_update_frequency()
