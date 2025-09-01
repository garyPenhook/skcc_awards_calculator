#!/usr/bin/env python3
"""W4GNS SKCC Logger - QSO Logging Application."""

import sys
import traceback
from pathlib import Path

# Add paths for imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main():
    """Main entry point with proper exception handling."""
    try:
        # Import and run the clean QSO form
        from gui.tk_qso_form_clean import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure all required packages are installed:")
        print("  pip install httpx beautifulsoup4")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error starting SKCC Logger: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("\nPlease report this error with the traceback above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
