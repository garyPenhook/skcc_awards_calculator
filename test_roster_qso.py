"""Test script for the roster-enabled QSO logger."""

import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.roster_qso_form import RosterQSOForm

def test_roster_manager():
    """Test basic roster manager functionality."""
    from utils.roster_manager import RosterManager
    
    print("Testing Roster Manager...")
    
    # Initialize roster manager
    rm = RosterManager()
    
    # Get status
    status = rm.get_status()
    print(f"Roster Status: {status}")
    
    # Test some sample lookups
    test_calls = ["W1AW", "KE7UAE", "VE3ABC", "G0XYZ"]
    
    for call in test_calls:
        result = rm.lookup_member(call)
        if result:
            print(f"✓ Found {call}: SKCC #{result['number']}")
        else:
            print(f"✗ Not found: {call}")
    
    # Test search functionality
    print(f"\nTesting search for 'W1':")
    results = rm.search_callsigns("W1", limit=5)
    for result in results:
        print(f"  {result['call']} - SKCC #{result['number']}")

def test_config_manager():
    """Test configuration manager."""
    from utils.config_manager import get_config
    
    print("\nTesting Config Manager...")
    
    config = get_config()
    print(f"Config directory: {config.get_data_dir()}")
    print(f"Default ADIF path: {config.get_default_adif_path()}")
    
    # Test setting and getting values
    config.set_setting('station_callsign', 'TEST123')
    retrieved = config.get_setting('station_callsign')
    print(f"Test setting - Set: TEST123, Retrieved: {retrieved}")

def main():
    """Main test function."""
    print("SKCC QSO Logger with Roster - Test Suite")
    print("=" * 50)
    
    try:
        test_config_manager()
        test_roster_manager()
        
        print("\n" + "=" * 50)
        print("Starting QSO Logger GUI...")
        
        # Launch the GUI
        app = RosterQSOForm()
        app.root.mainloop()
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
