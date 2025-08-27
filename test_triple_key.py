#!/usr/bin/env python3
"""Test script for Triple Key Awards functionality."""

import sys
from pathlib import Path

# Add backend to path
BACKEND_APP = Path(__file__).resolve().parent / "backend" / "app"
sys.path.insert(0, str(BACKEND_APP))

from services.skcc import (
    QSO, Member, calculate_triple_key_awards
)

def test_triple_key_awards():
    """Test Triple Key Awards calculation."""
    print("Testing Triple Key Awards calculation:")
    
    # Create test QSOs with different key types and dates
    qsos = [
        # Straight key contacts (valid after 2018-11-10) - simplified key types
        QSO(call="W1ABC", band="20M", mode="CW", date="20190101", skcc="1000", key_type="SK"),
        QSO(call="W2DEF", band="40M", mode="CW", date="20190102", skcc="2000", comment="SK"),
        QSO(call="W3GHI", band="15M", mode="CW", date="20190103", skcc="3000", key_type="STRAIGHT"),
        QSO(call="W4JKL", band="20M", mode="CW", date="20190104", skcc="4000", comment="STRAIGHT"),
        QSO(call="W5MNO", band="40M", mode="CW", date="20190105", skcc="5000", key_type="SK"),
        
        # Bug contacts
        QSO(call="N1PQR", band="20M", mode="CW", date="20190201", skcc="6000", key_type="BUG"),
        QSO(call="N2STU", band="40M", mode="CW", date="20190202", skcc="7000", comment="BUG"),
        QSO(call="N3VWX", band="15M", mode="CW", date="20190203", skcc="8000", key_type="BUG"),
        QSO(call="N4YZA", band="20M", mode="CW", date="20190204", skcc="9000", comment="BUG"),
        
        # Sideswiper contacts  
        QSO(call="K1BCD", band="20M", mode="CW", date="20190301", skcc="10000", key_type="SIDESWIPER"),
        QSO(call="K2EFG", band="40M", mode="CW", date="20190302", skcc="11000", comment="SIDESWIPER"),
        QSO(call="K3HIJ", band="15M", mode="CW", date="20190303", skcc="12000", key_type="COOTIE"),
        QSO(call="K4KLM", band="20M", mode="CW", date="20190304", skcc="13000", comment="COOTIE"),
        
        # Contacts before start date (should be excluded)
        QSO(call="W9OLD", band="20M", mode="CW", date="20180601", skcc="14000", key_type="SK"),
        
        # Non-SKCC member (should be excluded)
        QSO(call="W9NON", band="20M", mode="CW", date="20190501", key_type="BUG"),
        
        # Contact without key type specified (should be excluded)
        QSO(call="K5NKT", band="20M", mode="CW", date="20190601", skcc="15000"),
        
        # Additional contacts to build larger counts for testing
    ]
    
    # Add more contacts to reach higher counts for testing
    for i in range(20, 120):  # Add 100 more straight key contacts
        qsos.append(QSO(
            call=f"WA{i:02d}XY",
            band="20M",
            mode="CW", 
            date="20190401",
            skcc=str(20000 + i),
            key_type="SK"
        ))
    
    for i in range(120, 220):  # Add 100 bug contacts
        qsos.append(QSO(
            call=f"WB{i:02d}XY",
            band="20M",
            mode="CW",
            date="20190402", 
            skcc=str(20000 + i),
            key_type="BUG"
        ))
        
    for i in range(220, 320):  # Add 100 sideswiper contacts
        qsos.append(QSO(
            call=f"WC{i:02d}XY",
            band="20M",
            mode="CW",
            date="20190403",
            skcc=str(20000 + i),
            key_type="COOTIE"
        ))
    
    # Create test members
    members = [
        Member(call="W1ABC", number=1000),
        Member(call="W2DEF", number=2000),
        Member(call="W3GHI", number=3000),
        Member(call="W4JKL", number=4000),
        Member(call="W5MNO", number=5000),
        Member(call="N1PQR", number=6000),
        Member(call="N2STU", number=7000),
        Member(call="N3VWX", number=8000),
        Member(call="N4YZA", number=9000),
        Member(call="K1BCD", number=10000),
        Member(call="K2EFG", number=11000),
        Member(call="K3HIJ", number=12000),
        Member(call="K4KLM", number=13000),
        Member(call="W9OLD", number=14000),
        Member(call="K5NKT", number=15000),
    ]
    
    # Add members for the additional test contacts
    for i in range(20, 320):
        if i < 120:
            call = f"WA{i:02d}XY"
        elif i < 220:
            call = f"WB{i:02d}XY"
        else:
            call = f"WC{i:02d}XY"
        members.append(Member(call=call, number=20000 + i))
    
    # Calculate awards
    awards = calculate_triple_key_awards(qsos, members)
    
    print(f"  Found {len(awards)} Triple Key Award categories:")
    
    for award in awards:
        status = "✓" if award.achieved else "○"
        print(f"    {status} {award.name}: {award.current_count}/{award.threshold} ({award.percentage:.1f}%)")
        if award.achieved:
            print(f"      Sample contacts: {', '.join(award.members_worked[:5])}")
            if len(award.members_worked) > 5:
                print(f"      ... and {len(award.members_worked) - 5} more")

def test_key_type_detection():
    """Test key type detection from various fields."""
    print("\nTesting key type detection:")
    
    test_cases = [
        # Test QSOs with different key type indicators - simplified to core SKCC types
        (QSO(call="W1TEST", band="20M", mode="CW", date="20190101", skcc="1000", key_type="SK"), "straight"),
        (QSO(call="W2TEST", band="20M", mode="CW", date="20190101", skcc="2000", key_type="BUG"), "bug"),
        (QSO(call="W3TEST", band="20M", mode="CW", date="20190101", skcc="3000", key_type="SIDESWIPER"), "sideswiper"),
        (QSO(call="W4TEST", band="20M", mode="CW", date="20190101", skcc="4000", key_type="COOTIE"), "sideswiper"),
        (QSO(call="W5TEST", band="20M", mode="CW", date="20190101", skcc="5000", comment="SK"), "straight"),
        (QSO(call="W6TEST", band="20M", mode="CW", date="20190101", skcc="6000", comment="BUG"), "bug"),
        (QSO(call="W7TEST", band="20M", mode="CW", date="20190101", skcc="7000", comment="COOTIE"), "sideswiper"),
        (QSO(call="W8TEST", band="20M", mode="CW", date="20190101", skcc="8000", key_type="STRAIGHT"), "straight"),
        (QSO(call="W9TEST", band="20M", mode="CW", date="20190101", skcc="9000"), None),  # No key type
    ]
    
    members = [Member(call=f"W{i}TEST", number=i*1000) for i in range(1, 10)]
    
    for qso, expected_key_type in test_cases:
        # Create single QSO list for testing
        awards = calculate_triple_key_awards([qso], members)
        
        # Check which award category got a count
        detected_type = None
        for award in awards:
            if award.current_count > 0 and award.key_type != "overall":
                detected_type = award.key_type
                break
        
        status = "✓" if detected_type == expected_key_type else "✗"
        key_info = qso.key_type or qso.comment or "No key type"
        print(f"  {status} '{key_info}' -> {detected_type} (expected {expected_key_type})")

if __name__ == "__main__":
    test_key_type_detection()
    test_triple_key_awards()
    print("\nTriple Key Awards test complete!")
