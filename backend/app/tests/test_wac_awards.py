#!/usr/bin/env python3
"""Test WAC (Worked All Continents) Awards calculation."""

import sys
from pathlib import Path

# Add the backend app directory to Python path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from services.skcc import (
    QSO, Member, calculate_wac_awards, get_continent_from_call, get_continent_from_country
)
from datetime import datetime

def test_continent_detection():
    """Test continent detection from call signs and countries."""
    print("Testing continent detection...")
    
    test_cases = [
        ("W1AW", "NA", "United States"),
        ("VE1AAA", "NA", "Canada"),
        ("G0ABC", "EU", "England"),
        ("DL1ABC", "EU", "Germany"),
        ("JA1ABC", "AS", "Japan"),
        ("VK1ABC", "OC", "Australia"),
        ("ZS1ABC", "AF", "South Africa"),
        ("PY1ABC", "SA", "Brazil"),
    ]
    
    for call, expected_continent, expected_country in test_cases:
        continent = get_continent_from_call(call)
        print(f"  {call} -> {continent} (expected: {expected_continent})")
        assert continent == expected_continent, f"Expected {expected_continent} for {call}, got {continent}"
    
    print("✓ Continent detection tests passed")

def test_wac_basic():
    """Test basic WAC award calculation."""
    print("\nTesting basic WAC award calculation...")
    
    # Create test members
    members = [
        Member("W1TEST", 12345, "2010-01-01"),  # US
        Member("VE1TEST", 12346, "2010-01-01"), # Canada  
        Member("G0TEST", 12347, "2010-01-01"),  # England
        Member("DL1TEST", 12348, "2010-01-01"), # Germany
        Member("JA1TEST", 12349, "2010-01-01"), # Japan
        Member("VK1TEST", 12350, "2010-01-01"), # Australia
        Member("ZS1TEST", 12351, "2010-01-01"), # South Africa
        Member("PY1TEST", 12352, "2010-01-01"), # Brazil
    ]
    
    # Create test QSOs - work all 6 continents
    qsos = [
        QSO("W1TEST", "20M", "CW", "20120101", time_on="1200", tx_pwr="100"),       # NA
        QSO("VE1TEST", "20M", "CW", "20120102", time_on="1200", tx_pwr="100"),      # NA (additional)
        QSO("G0TEST", "20M", "CW", "20120103", time_on="1200", tx_pwr="100"),       # EU
        QSO("JA1TEST", "20M", "CW", "20120104", time_on="1200", tx_pwr="100"),      # AS
        QSO("VK1TEST", "20M", "CW", "20120105", time_on="1200", tx_pwr="100"),      # OC
        QSO("ZS1TEST", "20M", "CW", "20120106", time_on="1200", tx_pwr="100"),      # AF
        QSO("PY1TEST", "20M", "CW", "20120107", time_on="1200", tx_pwr="100"),      # SA
    ]
    
    # Debug: Print QSO details
    print(f"Test QSOs:")
    for qso in qsos:
        if qso.call:
            continent = get_continent_from_call(qso.call)
            print(f"  {qso.call} -> {continent} on {qso.band}")
        else:
            print(f"  No call sign in QSO")
    
    awards = calculate_wac_awards(qsos, members)
    
    # Debug: print all awards
    print(f"Generated {len(awards)} awards:")
    for award in awards:
        print(f"  {award.name} ({award.award_type}, band={award.band}) - {award.current_continents}/6")
    
    # Should have overall WAC award achieved
    overall_wac = next((a for a in awards if a.award_type == "WAC" and a.band is None), None)
    assert overall_wac is not None, "Overall WAC award not found"
    assert overall_wac.achieved, f"WAC award should be achieved, got {overall_wac.current_continents}/6 continents"
    assert overall_wac.current_continents == 6, f"Expected 6 continents, got {overall_wac.current_continents}"
    assert set(overall_wac.continents_worked) == {"AF", "AS", "EU", "NA", "OC", "SA"}, f"Unexpected continents: {overall_wac.continents_worked}"
    
    print(f"✓ Overall WAC: {overall_wac.current_continents}/6 continents - {'ACHIEVED' if overall_wac.achieved else 'Not achieved'}")
    print(f"  Continents: {', '.join(sorted(overall_wac.continents_worked))}")
    
    # Check 20M band endorsement
    band_20m = next((a for a in awards if a.award_type == "WAC-20M" and a.band == "20M"), None)
    if band_20m is None:
        print("Available awards:")
        for award in awards:
            print(f"  - {award.award_type} (band: {award.band})")
    assert band_20m is not None, "20M band WAC award not found"
    assert band_20m.achieved, f"20M WAC should be achieved, got {band_20m.current_continents}/6 continents"
    
    print(f"✓ 20M Band WAC: {band_20m.current_continents}/6 continents - {'ACHIEVED' if band_20m.achieved else 'Not achieved'}")

def test_wac_qrp():
    """Test WAC QRP award calculation."""
    print("\nTesting WAC QRP award calculation...")
    
    # Create test members
    members = [
        Member("W1TEST", 12345, "2010-01-01"),  # US
        Member("G0TEST", 12347, "2010-01-01"),  # England
        Member("JA1TEST", 12349, "2010-01-01"), # Japan
        Member("VK1TEST", 12350, "2010-01-01"), # Australia
        Member("ZS1TEST", 12351, "2010-01-01"), # South Africa
        Member("PY1TEST", 12352, "2010-01-01"), # Brazil
    ]
    
    # Create test QSOs - all QRP (5W or less)
    qsos = [
        QSO("W1TEST", "20M", "CW", "20120101", time_on="1200", tx_pwr="5"),      # NA - QRP
        QSO("G0TEST", "20M", "CW", "20120103", time_on="1200", tx_pwr="3"),      # EU - QRP  
        QSO("JA1TEST", "20M", "CW", "20120104", time_on="1200", tx_pwr="5"),     # AS - QRP
        QSO("VK1TEST", "20M", "CW", "20120105", time_on="1200", tx_pwr="4"),     # OC - QRP
        QSO("ZS1TEST", "20M", "CW", "20120106", time_on="1200", tx_pwr="5"),     # AF - QRP
        QSO("PY1TEST", "20M", "CW", "20120107", time_on="1200", tx_pwr="2"),     # SA - QRP
    ]
    
    awards = calculate_wac_awards(qsos, members)
    
    # Check overall QRP award
    qrp_wac = next((a for a in awards if a.award_type == "WAC-QRP" and a.band is None), None)
    assert qrp_wac is not None, "QRP WAC award not found"
    assert qrp_wac.achieved, f"QRP WAC should be achieved, got {qrp_wac.current_continents}/6 continents"
    assert qrp_wac.current_continents == 6, f"Expected 6 QRP continents, got {qrp_wac.current_continents}"
    
    print(f"✓ QRP WAC: {qrp_wac.current_continents}/6 continents - {'ACHIEVED' if qrp_wac.achieved else 'Not achieved'}")
    
    # Check 20M QRP band endorsement
    qrp_20m = next((a for a in awards if a.award_type == "WAC-20M-QRP" and a.band == "20M"), None)
    assert qrp_20m is not None, "20M QRP WAC award not found"
    assert qrp_20m.achieved, f"20M QRP WAC should be achieved, got {qrp_20m.current_continents}/6 continents"
    
    print(f"✓ 20M QRP WAC: {qrp_20m.current_continents}/6 continents - {'ACHIEVED' if qrp_20m.achieved else 'Not achieved'}")

def test_wac_date_filter():
    """Test WAC award date filtering (valid after Oct 9, 2011)."""
    print("\nTesting WAC award date filtering...")
    
    # Create test members
    members = [
        Member("W1TEST", 12345, "2010-01-01"),
        Member("G0TEST", 12347, "2010-01-01"),
    ]
    
    # Create QSOs before and after start date
    qsos = [
        QSO("W1TEST", "20M", "CW", "20110101", time_on="1200"),  # Before Oct 9, 2011 - invalid
        QSO("G0TEST", "20M", "CW", "20111010", time_on="1200"),  # After Oct 9, 2011 - valid
    ]
    
    awards = calculate_wac_awards(qsos, members)
    
    overall_wac = next((a for a in awards if a.award_type == "WAC" and a.band is None), None)
    assert overall_wac is not None, "Overall WAC award not found"
    assert overall_wac.current_continents == 1, f"Expected 1 continent (only post-date QSO), got {overall_wac.current_continents}"
    assert "EU" in overall_wac.continents_worked, "EU should be worked (G0TEST QSO)"
    assert "NA" not in overall_wac.continents_worked, "NA should not be worked (pre-date QSO)"
    
    print(f"✓ Date filtering: {overall_wac.current_continents} continents (filtered out pre-Oct 2011 QSOs)")

def test_wac_partial_progress():
    """Test WAC award with partial continent progress."""
    print("\nTesting WAC award partial progress...")
    
    # Create test members
    members = [
        Member("W1TEST", 12345, "2010-01-01"),  # US (NA)
        Member("G0TEST", 12347, "2010-01-01"),  # England (EU)
        Member("JA1TEST", 12349, "2010-01-01"), # Japan (AS)
    ]
    
    # Create QSOs for only 3 continents
    qsos = [
        QSO("W1TEST", "20M", "CW", "20120101", time_on="1200"),
        QSO("G0TEST", "20M", "CW", "20120103", time_on="1200"),
        QSO("JA1TEST", "20M", "CW", "20120104", time_on="1200"),
    ]
    
    awards = calculate_wac_awards(qsos, members)
    
    overall_wac = next((a for a in awards if a.award_type == "WAC" and a.band is None), None)
    assert overall_wac is not None, "Overall WAC award not found"
    assert not overall_wac.achieved, "WAC award should not be achieved with only 3 continents"
    assert overall_wac.current_continents == 3, f"Expected 3 continents, got {overall_wac.current_continents}"
    assert set(overall_wac.continents_worked) == {"AS", "EU", "NA"}, f"Unexpected continents: {overall_wac.continents_worked}"
    
    print(f"✓ Partial progress: {overall_wac.current_continents}/6 continents - Not achieved (as expected)")
    print(f"  Continents worked: {', '.join(sorted(overall_wac.continents_worked))}")
    print(f"  Still need: {', '.join(sorted({'AF', 'OC', 'SA'} - set(overall_wac.continents_worked)))}")

if __name__ == "__main__":
    print("Running WAC Awards tests...\n")
    
    test_continent_detection()
    test_wac_basic()
    test_wac_qrp() 
    test_wac_date_filter()
    test_wac_partial_progress()
    
    print("\n✅ All WAC Awards tests passed!")
