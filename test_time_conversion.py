#!/usr/bin/env python3
"""Test script to verify time conversion functionality."""

from datetime import datetime, timezone
import time

def test_time_conversion():
    """Test the time conversion logic used in the QSO logger."""
    print("Testing Time Conversion Logic")
    print("=" * 40)
    
    # Method 1: Direct UTC (old method)
    utc_direct = datetime.now(timezone.utc)
    print(f"Direct UTC:        {utc_direct.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Method 2: Local to UTC conversion (new method)
    local_now = datetime.now()  # Local time (includes DST)
    utc_converted = local_now.astimezone(timezone.utc)  # Convert to UTC
    print(f"Local time:        {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Converted to UTC:  {utc_converted.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Test round-trip conversion
    local_again = utc_converted.astimezone()  # Convert back to local
    print(f"Back to local:     {local_again.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Show timezone info
    print(f"\nTimezone info:")
    print(f"Local timezone:    {local_now.astimezone().tzinfo}")
    print(f"UTC offset:        {local_now.astimezone().strftime('%z')}")
    print(f"DST active:        {time.daylight and bool(time.localtime().tm_isdst)}")
    
    # Verify they're close (should be within a few seconds)
    time_diff = abs((utc_converted - utc_direct).total_seconds())
    print(f"\nTime difference:   {time_diff:.2f} seconds")
    
    if time_diff < 5:  # Within 5 seconds is fine
        print("✓ Time conversion working correctly!")
    else:
        print("✗ Time conversion may have issues")

if __name__ == "__main__":
    test_time_conversion()
