#!/usr/bin/env python3
"""Quick test script for QSO logger roster functionality."""

import sys
from pathlib import Path

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.roster_manager import RosterManager

def test_roster_functions():
    """Test the roster manager functions used by QSO logger."""
    print("Testing Roster Manager for QSO Logger...")
    
    try:
        # Initialize roster manager
        rm = RosterManager()
        print("✓ Roster manager initialized")
        
        # Get status
        status = rm.get_status()
        print(f"✓ Roster status: {status}")
        
        # Test search functionality
        print("\nTesting search for 'W1':")
        results = rm.search_callsigns("W1", limit=5)
        for result in results:
            print(f"  {result['call']} - SKCC #{result['number']}")
        
        # Test lookup functionality
        print(f"\nTesting lookup for 'W1AW':")
        result = rm.lookup_member("W1AW")
        if result:
            print(f"  Found: SKCC #{result['number']}")
        else:
            print("  Not found")
            
        print("\n✓ All roster functions working correctly")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_roster_functions()
    sys.exit(0 if success else 1)
