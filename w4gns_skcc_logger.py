#!/usr/bin/env python3
"""W4GNS SKCC Logger - QSO Logging Application."""

import sys
from pathlib import Path

# Add paths for imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import and run the clean QSO form
from gui.tk_qso_form_clean import main

if __name__ == "__main__":
    main()
