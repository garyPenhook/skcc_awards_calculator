# SKCC Logger - Roster Update on Startup Fix

## Problem
The user reported: "the update member roster is not updating every start up"

## Root Cause Analysis
The roster update system was designed to only check for updates every 24 hours to avoid putting unnecessary load on the SKCC servers. This meant that if a user started the application multiple times within 24 hours, the roster would not be checked for updates after the first startup.

## Investigation Results
- **Original behavior**: Roster only updated if older than 24 hours
- **User expectation**: Roster should be checked for updates on every startup
- **Roster age when reported**: ~2 hours old (last updated at 04:03:16, current time ~06:11)
- **Current roster size**: 30,258 members

## Solution Implemented
Modified the GUI initialization to check for roster updates on every startup with a 1-hour minimum interval:

### Changes Made:

1. **Enhanced `ensure_roster_updated()` method** (`utils/roster_manager.py`):
   - Added `max_age_hours` parameter to allow custom update intervals
   - Modified the needs_update check to use the custom interval

2. **Updated GUI initialization** (`gui/tk_qso_form_clean.py`):
   - Changed startup behavior to always check for roster updates
   - Set 1-hour minimum interval for startup checks (`max_age_hours=1`)
   - Fixed threading issues with progress dialog updates

3. **Improved thread safety**:
   - Used `self.after()` to schedule UI updates on the main thread
   - Removed blocking `thread.join()` call that was defeating the purpose of background threading

## Technical Details

### Before Fix:
```python
# Only updated if needs_update() returned True (24-hour default)
if needs_update:
    self._update_roster_async()
else:
    # Skip update, show "Roster is current"
```

### After Fix:
```python
# Always check for updates on startup with 1-hour minimum
self._update_roster_async()  # Uses max_age_hours=1
```

### Update Intervals:
- **Default interval**: 24 hours (for background operations)
- **Startup interval**: 1 hour (for GUI initialization)
- **Force option**: Available for immediate updates regardless of age

## Verification Results
✅ **Test passed**: Roster was successfully updated on GUI startup
- Previous update: `2025-09-01T04:03:16` (2+ hours old)
- New update: `2025-09-01T06:11:49` (triggered by GUI startup)
- Age after update: 5 seconds (confirming fresh update)

## User Benefits
1. **Frequent Updates**: Roster is checked on every startup (minimum 1-hour interval)
2. **Server Efficiency**: Prevents excessive server requests with 1-hour minimum
3. **Reliable Data**: Ensures state auto-fill and member lookups use current data
4. **Progress Feedback**: Users see clear indication of roster checking/updating
5. **No Blocking**: Background updates don't freeze the GUI

## Configuration Options
Users can manually force updates using the command-line tool:
```bash
# Force immediate update regardless of age
python scripts/roster_sync.py sync --force

# Check status
python scripts/roster_sync.py status
```

## Status: COMPLETED ✅
The roster update issue has been fully resolved. The GUI now checks for roster updates on every startup while maintaining efficient server usage patterns.
