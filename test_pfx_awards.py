#!/usr/bin/env python3
"""Test script for PFX Awards functionality."""

import sys
from pathlib import Path

# Add backend to path
BACKEND_APP = Path(__file__).resolve().parent / "backend" / "app"
sys.path.insert(0, str(BACKEND_APP))

from services.skcc import (
    QSO, Member, extract_prefix, calculate_pfx_awards
)

def test_prefix_extraction():
    """Test call sign prefix extraction according to PFX rules."""
    print("Testing call sign prefix extraction:")
    
    test_calls = [
        ("AC2C", "AC2"),
        ("N6WK", "N6"),
        ("DU3/W5LFA", "W5"),  # Use part after /
        ("2D0YLX", "2D0"),
        ("S51AF", "S51"),
        ("K5ZMD/7", "K5"),    # Portable, use base
        ("W4/IB4DX", "IB4"),  # Special case: use part after /
        ("VE1ABC", "VE1"),
        ("JA1XYZ", "JA1"),
        ("G0ABC", "G0"),
        ("HL9DX", "HL9"),
        ("K1ABC/MM", "K1"),   # Maritime mobile
        ("VK2DEF/P", "VK2"),  # Portable
        ("", None),           # Empty
        ("INVALID", None),    # No digits
    ]
    
    for call, expected in test_calls:
        result = extract_prefix(call)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {call} -> {result} (expected {expected})")

def test_pfx_awards_calculation():
    """Test PFX Awards calculation."""
    print("\nTesting PFX Awards calculation:")
    
    # Create test QSOs with various prefixes and SKCC numbers
    qsos = [
        # Different prefixes with various SKCC numbers
        QSO(call="W1ABC", band="20M", mode="CW", date="20140101", skcc="1000"),      # W1, 1000 points
        QSO(call="W2DEF", band="40M", mode="CW", date="20140102", skcc="2000"),     # W2, 2000 points  
        QSO(call="W3GHI", band="15M", mode="CW", date="20140103", skcc="3000"),     # W3, 3000 points
        QSO(call="W4JKL", band="20M", mode="CW", date="20140104", skcc="4000"),     # W4, 4000 points
        QSO(call="W5MNO", band="40M", mode="CW", date="20140105", skcc="5000"),     # W5, 5000 points
        QSO(call="W6PQR", band="20M", mode="CW", date="20140106", skcc="6000"),     # W6, 6000 points
        QSO(call="W7STU", band="15M", mode="CW", date="20140107", skcc="7000"),     # W7, 7000 points
        QSO(call="W8VWX", band="40M", mode="CW", date="20140108", skcc="8000"),     # W8, 8000 points
        QSO(call="W9YZA", band="20M", mode="CW", date="20140109", skcc="9000"),     # W9, 9000 points
        QSO(call="W0BCD", band="15M", mode="CW", date="20140110", skcc="10000"),    # W0, 10000 points
        
        # Different call areas with same prefix (should use highest number)
        QSO(call="K1EFG", band="20M", mode="CW", date="20140201", skcc="15000"),    # K1, 15000 points
        QSO(call="K1HIJ", band="40M", mode="CW", date="20140202", skcc="12000"),    # K1, 12000 points (lower, won't count)
        
        # International prefixes
        QSO(call="VE1KLM", band="20M", mode="CW", date="20140301", skcc="20000"),   # VE1, 20000 points
        QSO(call="G0NOP", band="40M", mode="CW", date="20140302", skcc="25000"),    # G0, 25000 points
        QSO(call="JA1QRS", band="15M", mode="CW", date="20140303", skcc="30000"),   # JA1, 30000 points
        
        # Multiple contacts same prefix, different numbers
        QSO(call="N6TUV", band="20M", mode="CW", date="20140401", skcc="35000"),    # N6, 35000 points
        QSO(call="N6WXY", band="40M", mode="CW", date="20140402", skcc="40000"),    # N6, 40000 points (higher)
        
        # Before start date (should be excluded)
        QSO(call="W1OLD", band="20M", mode="CW", date="20120601", skcc="50000"),    # Before 2013
        
        # Non-SKCC member (should be excluded)
        QSO(call="W1NON", band="20M", mode="CW", date="20140501"),                  # No SKCC number
    ]
    
    # Create test members
    members = [
        Member(call="W1ABC", number=1000),
        Member(call="W2DEF", number=2000),
        Member(call="W3GHI", number=3000),
        Member(call="W4JKL", number=4000),
        Member(call="W5MNO", number=5000),
        Member(call="W6PQR", number=6000),
        Member(call="W7STU", number=7000),
        Member(call="W8VWX", number=8000),
        Member(call="W9YZA", number=9000),
        Member(call="W0BCD", number=10000),
        Member(call="K1EFG", number=15000),
        Member(call="K1HIJ", number=12000),
        Member(call="VE1KLM", number=20000),
        Member(call="G0NOP", number=25000),
        Member(call="JA1QRS", number=30000),
        Member(call="N6TUV", number=35000),
        Member(call="N6WXY", number=40000),
        Member(call="W1OLD", number=50000),
    ]
    
    # Calculate awards
    awards = calculate_pfx_awards(qsos, members)
    
    # Filter to show relevant awards
    relevant_awards = [a for a in awards if a.current_score > 0 or a.achieved]
    
    print(f"  Found {len(relevant_awards)} PFX Awards with progress:")
    
    # Calculate expected score manually for verification
    # Expected prefixes and their highest scores:
    # W1: 1000, W2: 2000, W3: 3000, W4: 4000, W5: 5000, 
    # W6: 6000, W7: 7000, W8: 8000, W9: 9000, W0: 10000,
    # K1: 15000, VE1: 20000, G0: 25000, JA1: 30000, N6: 40000
    # Total: 1000+2000+3000+4000+5000+6000+7000+8000+9000+10000+15000+20000+25000+30000+40000 = 185000
    
    overall_awards = [a for a in relevant_awards if a.band is None]
    if overall_awards:
        first_award = overall_awards[0]
        print(f"  Expected total score: 185,000")
        print(f"  Actual total score: {first_award.current_score:,}")
        print(f"  Unique prefixes: {first_award.unique_prefixes}")
    
    for award in relevant_awards[:10]:  # Show first 10 to avoid clutter
        status = "✓" if award.achieved else "○"
        band_text = f" on {award.band}" if award.band else ""
        print(f"    {status} {award.name}{band_text}: {award.current_score:,}/{award.threshold:,}")
        if award.achieved:
            prefixes_preview = ', '.join(award.prefixes_worked[:5])
            if len(award.prefixes_worked) > 5:
                prefixes_preview += f" ... (+{len(award.prefixes_worked)-5} more)"
            print(f"      Prefixes: {prefixes_preview}")

if __name__ == "__main__":
    test_prefix_extraction()
    test_pfx_awards_calculation()
    print("\nPFX Awards test complete!")
