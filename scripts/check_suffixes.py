#!/usr/bin/env python
"""Check what suffixes are actually in the roster vs ADIF file."""

import sys
from pathlib import Path
import asyncio

# Add backend app to path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

from services.skcc import fetch_member_roster, parse_adif
import httpx
from bs4 import BeautifulSoup


async def check_suffixes():
    print("=== Checking SKCC Number Suffixes ===")

    # Parse our ADIF file
    adif_file = Path(__file__).parent / "main.adi"
    with open(adif_file, "r", encoding="utf-8") as f:
        content = f.read()
    qsos = parse_adif(content)

    # Get raw HTML to see actual suffixes in roster
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://www.skccgroup.com/membership_data/membership_roster.php"
        )
        html_content = response.text

    soup = BeautifulSoup(html_content, "html.parser")

    # Collect test cases from our ADIF
    test_cases = []
    for qso in qsos[:10]:  # First 10 QSOs
        if qso.skcc and qso.call:
            test_cases.append((qso.call, qso.skcc))

    print(f"Checking {len(test_cases)} test cases from ADIF:")

    # Find each one in the roster HTML
    for call, adif_skcc in test_cases:
        print(f"\n{call}: ADIF has '{adif_skcc}'")

        # Find this call in the roster
        found = False
        rows = soup.find_all("tr")
        for tr in rows:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2 and len(cells) >= 2:
                roster_skcc = cells[0]
                roster_call = cells[1] if len(cells) > 1 else ""

                if roster_call == call:
                    print(f"  Roster has: '{roster_skcc}' for {roster_call}")
                    if roster_skcc == adif_skcc:
                        print(f"  ✓ MATCH")
                    else:
                        print(f"  ✗ MISMATCH! ADIF: {adif_skcc}, Roster: {roster_skcc}")
                    found = True
                    break

        if not found:
            print(f"  NOT FOUND in roster")


if __name__ == "__main__":
    asyncio.run(check_suffixes())
