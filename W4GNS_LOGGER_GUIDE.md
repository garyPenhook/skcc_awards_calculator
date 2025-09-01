# W4GNS SKCC Logger - Usage Guide

## Main Logger Application

**Use this file:** `w4gns_skcc_logger.py`

```bash
python w4gns_skcc_logger.py
```

This is the **official W4GNS SKCC Logger** with all enhanced features:

## Features Included
- ✅ **QSO Logging**: Complete QSO entry with timing
- ✅ **Cluster Spots**: Real-time RBN spots with SKCC filtering
- ✅ **State Auto-fill**: Automatic state lookup from SKCC roster
- ✅ **Roster Updates**: Checks on startup (updates if older than 1 hour)
- ✅ **Duplicate Filtering**: Clean spots display without repeated callsigns
- ✅ **Two-Column Layout**: QSO form on left, spots/history on right
- ✅ **Backup Management**: Automatic ADIF backup functionality
- ✅ **Progress Dialogs**: Startup progress with roster status display

## Alternative Launch Methods

### Batch Files (Windows)
```bash
# Main logger
run_qso_logger.bat

# Same as above, alternative name
run_roster_qso.bat

# Awards calculator (different application)
run_gui.bat
```

### Direct Python
```bash
# Main W4GNS SKCC Logger
python w4gns_skcc_logger.py

# Awards calculator
python scripts/gui.py
```

## What Was Removed
To eliminate confusion, the following redundant files were removed:
- ❌ `gui/tk_qso_form.py` - Old version without cluster spots
- ❌ `gui/roster_qso_form.py` - Separate form (functionality merged)
- ❌ `test_roster_qso.py` - Non-existent test file

## Key Files
- **Main App**: `w4gns_skcc_logger.py` 
- **GUI Implementation**: `gui/tk_qso_form_clean.py`
- **Cluster Client**: `utils/cluster_client.py`
- **Roster Manager**: `utils/roster_manager.py`

## Quick Start
1. Download the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python w4gns_skcc_logger.py`
4. Start logging QSOs with real-time cluster spots!

---
**This is the ONLY logger you need for W4GNS SKCC operations.**
