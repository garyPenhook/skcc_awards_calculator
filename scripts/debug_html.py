#!/usr/bin/env python
"""Debug HTML roster parsing to see why members aren't being found."""

import sys
from pathlib import Path

# Add backend app to path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

import asyncio

import httpx
from bs4 import BeautifulSoup
from services.skcc import DEFAULT_ROSTER_URL, _parse_roster_text


async def debug_html_parsing():
    print("=== Debugging HTML Roster Parsing ===")

    # Fetch the raw HTML
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(DEFAULT_ROSTER_URL)
        html_content = response.text

    print(f"HTML content length: {len(html_content)} characters")

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    rows = soup.find_all("tr")
    print(f"Found {len(rows)} table rows")

    # Look for our test numbers
    test_numbers = [660, 1395, 13613, 24472, 25995]
    found_rows = []

    for i, tr in enumerate(rows):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2:
            try:
                number = int(cells[0])
                if number in test_numbers:
                    found_rows.append((i, number, cells))
            except ValueError:
                continue

    print(f"\nFound {len(found_rows)} rows with our test numbers:")
    for row_idx, number, cells in found_rows:
        print(f"  Row {row_idx}: {number} -> {cells[:5]}")

    # Show some sample rows to understand the structure
    print("\nSample rows (first 10 data rows):")
    data_rows = 0
    for i, tr in enumerate(rows):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2:
            try:
                number = int(cells[0])
                data_rows += 1
                if data_rows <= 10:
                    print(f"  Row {i}: {cells[:5]}")
            except ValueError:
                continue

    # Test the parsing function directly
    print("\n=== Testing _parse_roster_text function ===")
    members = _parse_roster_text(html_content)
    print(f"Parsed {len(members)} members")

    # Check for our test numbers
    number_to_member = {m.number: m for m in members}
    print("\nChecking for test numbers:")
    for num in test_numbers:
        if num in number_to_member:
            member = number_to_member[num]
            print(f"  {num}: FOUND - {member.call}")
        else:
            print(f"  {num}: NOT FOUND")

    # Check ranges around our test numbers to see if there are gaps
    print("\nChecking number ranges around test numbers:")
    for num in test_numbers:
        print(f"\nAround {num}:")
        for offset in range(-5, 6):
            check_num = num + offset
            if check_num in number_to_member:
                marker = "***" if check_num == num else "   "
                member = number_to_member[check_num]
                print(f"  {marker} {check_num}: {member.call}")

    # Count total gaps in number sequence
    all_numbers = sorted(number_to_member.keys())
    gaps = []
    for i in range(len(all_numbers) - 1):
        if all_numbers[i + 1] - all_numbers[i] > 1:
            gap_start = all_numbers[i] + 1
            gap_end = all_numbers[i + 1] - 1
            gaps.append((gap_start, gap_end))

    print(f"\nFound {len(gaps)} gaps in member numbering")
    print(f"Total numbers that should exist (1 to {max(all_numbers)}): {max(all_numbers)}")
    print(f"Actual members in roster: {len(all_numbers)}")
    print(f"Missing member count: {max(all_numbers) - len(all_numbers)}")

    # Show some gaps
    print("\nSample gaps (first 10):")
    for i, (start, end) in enumerate(gaps[:10]):
        print(f"  Gap {i+1}: {start}-{end} ({end-start+1} numbers)")

    # Show first few parsed members
    print("\nFirst 10 parsed members:")
    for i, member in enumerate(members[:10]):
        print(f"  {member.number}: {member.call}")


if __name__ == "__main__":
    asyncio.run(debug_html_parsing())
