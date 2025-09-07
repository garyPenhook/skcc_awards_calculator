#!/usr/bin/env python3
"""Test script for Rag Chew Awards functionality."""

import sys
from pathlib import Path

# Add backend to path
BACKEND_APP = Path(__file__).resolve().parent / "backend" / "app"
sys.path.insert(0, str(BACKEND_APP))

from services.skcc import QSO, Member, calculate_rag_chew_awards


def test_rag_chew_awards():
    """Test Rag Chew Awards calculation."""
    print("Testing Rag Chew Awards calculation:")

    # Create test QSOs with different durations
    qsos = [
        # Valid rag chew QSOs (30+ minutes after 2013-07-01)
        QSO(
            call="W1ABC",
            band="20M",
            mode="CW",
            date="20140101",
            skcc="1000",
            time_on="1200",
            duration_minutes=35,
        ),
        QSO(
            call="W2DEF",
            band="40M",
            mode="CW",
            date="20140102",
            skcc="2000",
            time_on="1300",
            duration_minutes=45,
        ),
        QSO(
            call="W3GHI",
            band="15M",
            mode="CW",
            date="20140103",
            skcc="3000",
            time_on="1400",
            duration_minutes=60,
        ),
        QSO(
            call="W4JKL",
            band="20M",
            mode="CW",
            date="20140104",
            skcc="4000",
            time_on="1500",
            duration_minutes=30,
        ),  # Exactly 30 min
        QSO(
            call="W5MNO",
            band="40M",
            mode="CW",
            date="20140105",
            skcc="5000",
            time_on="1600",
            duration_minutes=90,
        ),
        # Different band
        QSO(
            call="W6PQR",
            band="80M",
            mode="CW",
            date="20140201",
            skcc="6000",
            time_on="1700",
            duration_minutes=40,
        ),
        QSO(
            call="W7STU",
            band="80M",
            mode="CW",
            date="20140202",
            skcc="7000",
            time_on="1800",
            duration_minutes=50,
        ),
        # QSOs too short (less than 30 minutes - should be excluded)
        QSO(
            call="W8SHORT",
            band="20M",
            mode="CW",
            date="20140301",
            skcc="8000",
            time_on="1900",
            duration_minutes=25,
        ),
        QSO(
            call="W9SHORT",
            band="40M",
            mode="CW",
            date="20140302",
            skcc="9000",
            time_on="2000",
            duration_minutes=15,
        ),
        # QSOs before start date (should be excluded)
        QSO(
            call="W0OLD",
            band="20M",
            mode="CW",
            date="20130601",
            skcc="10000",
            time_on="2100",
            duration_minutes=60,
        ),
        # Non-SKCC member (should be excluded)
        QSO(
            call="W1NON",
            band="20M",
            mode="CW",
            date="20140401",
            time_on="2200",
            duration_minutes=45,
        ),
        # QSO without duration (should be excluded)
        QSO(call="K1NODUR", band="20M", mode="CW", date="20140501", skcc="11000"),
        # Additional QSOs to build larger totals for testing awards
        QSO(
            call="N1AAA",
            band="20M",
            mode="CW",
            date="20140601",
            skcc="12000",
            duration_minutes=120,
        ),  # 2 hours
        QSO(
            call="N2BBB",
            band="40M",
            mode="CW",
            date="20140602",
            skcc="13000",
            duration_minutes=180,
        ),  # 3 hours
        QSO(
            call="N3CCC",
            band="15M",
            mode="CW",
            date="20140603",
            skcc="14000",
            duration_minutes=150,
        ),  # 2.5 hours
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
        Member(call="W8SHORT", number=8000),
        Member(call="W9SHORT", number=9000),
        Member(call="W0OLD", number=10000),
        Member(call="K1NODUR", number=11000),
        Member(call="N1AAA", number=12000),
        Member(call="N2BBB", number=13000),
        Member(call="N3CCC", number=14000),
    ]

    # Calculate awards
    awards = calculate_rag_chew_awards(qsos, members)

    # Calculate expected total minutes manually for verification
    # Valid QSOs: 35+45+60+30+90+40+50+120+180+150 = 800 minutes
    expected_total = 35 + 45 + 60 + 30 + 90 + 40 + 50 + 120 + 180 + 150

    print(f"  Expected total minutes: {expected_total}")

    # Filter to show relevant awards (with progress or achieved)
    relevant_awards = [a for a in awards if a.current_minutes > 0 or a.achieved]

    print(f"  Found {len(relevant_awards)} Rag Chew Awards with progress:")

    # Show overall awards first
    overall_awards = [a for a in relevant_awards if a.band is None]
    print("  Overall Awards:")
    for award in overall_awards[:5]:  # Show first 5 levels
        status = "✓" if award.achieved else "○"
        percentage = (award.current_minutes / award.threshold) * 100
        print(
            f"    {status} {award.name}: {award.current_minutes}/{award.threshold} minutes ({percentage:.1f}%) - {award.qso_count} QSOs"
        )

    # Show band endorsements
    band_awards = [a for a in relevant_awards if a.band is not None]
    if band_awards:
        print("  Band Endorsements:")
        for award in band_awards[:10]:  # Show first 10 band awards
            status = "✓" if award.achieved else "○"
            percentage = (award.current_minutes / award.threshold) * 100
            print(
                f"    {status} {award.name} on {award.band}: {award.current_minutes}/{award.threshold} minutes ({percentage:.1f}%)"
            )


def test_duration_validation():
    """Test duration requirements and validation."""
    print("\nTesting duration validation:")

    test_cases = [
        # (duration_minutes, expected_valid, description)
        (30, True, "Exactly 30 minutes (minimum)"),
        (35, True, "35 minutes (valid)"),
        (29, False, "29 minutes (too short)"),
        (25, False, "25 minutes (too short)"),
        (60, True, "60 minutes (1 hour)"),
        (120, True, "120 minutes (2 hours)"),
        (None, False, "No duration specified"),
    ]

    base_qso = QSO(call="W1TEST", band="20M", mode="CW", date="20140101", skcc="1000")
    member = Member(call="W1TEST", number=1000)

    for duration, expected_valid, description in test_cases:
        # Create QSO with specific duration
        if duration is not None:
            test_qso = QSO(
                call=base_qso.call,
                band=base_qso.band,
                mode=base_qso.mode,
                date=base_qso.date,
                skcc=base_qso.skcc,
                duration_minutes=duration,
            )
        else:
            test_qso = base_qso

        # Test with single QSO
        awards = calculate_rag_chew_awards([test_qso], [member])

        # Check if any award has progress (indicating QSO was counted)
        has_progress = any(award.current_minutes > 0 for award in awards)

        status = "✓" if has_progress == expected_valid else "✗"
        result_text = "counted" if has_progress else "not counted"
        print(
            f"  {status} {description}: {result_text} (expected {'valid' if expected_valid else 'invalid'})"
        )


if __name__ == "__main__":
    test_duration_validation()
    test_rag_chew_awards()
    print("\nRag Chew Awards test complete!")
