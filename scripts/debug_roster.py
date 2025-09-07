#!/usr/bin/env python
"""Debug roster fetching to verify we're getting the complete membership data."""

import sys
from pathlib import Path

# Add backend app to path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

from services.skcc import fetch_member_roster, DEFAULT_ROSTER_URL, FALLBACK_ROSTER_URLS
import asyncio
import httpx


async def debug_roster():
    print("=== Debugging SKCC Roster Fetching ===")

    # Test the default URL first
    print(f"\nTesting default roster URL: {DEFAULT_ROSTER_URL}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(DEFAULT_ROSTER_URL)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"Content-Length: {len(response.text)} characters")

            # Show first few lines
            lines = response.text.split("\n")[:10]
            print(f"First 10 lines:")
            for i, line in enumerate(lines, 1):
                print(f"  {i}: {line[:100]}")

    except Exception as e:
        print(f"Error fetching default URL: {e}")

    # Test fallback URLs
    for url in FALLBACK_ROSTER_URLS:
        print(f"\nTesting fallback URL: {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"Content-Length: {len(response.text)} characters")
        except Exception as e:
            print(f"Error: {e}")

    # Test our parsing
    print(f"\n=== Testing Roster Parsing ===")
    members = await fetch_member_roster()
    print(f"Total members parsed: {len(members)}")

    # Test specific numbers that should exist
    test_numbers = [660, 1395, 13613, 24472, 25995, 29650, 29236]
    print(f"\nTesting specific SKCC numbers from your log:")

    number_to_member = {m.number: m for m in members}

    for num in test_numbers:
        if num in number_to_member:
            member = number_to_member[num]
            print(f"  {num}: FOUND - {member.call}")
        else:
            print(f"  {num}: NOT FOUND")

    # Show number ranges and recent additions
    numbers = [m.number for m in members]
    print(f"\nRoster statistics:")
    print(f"  Number range: {min(numbers)} to {max(numbers)}")
    print(f"  Total members: {len(numbers)}")
    print(f"  Members > 29000: {len([n for n in numbers if n > 29000])}")
    print(f"  Members > 30000: {len([n for n in numbers if n > 30000])}")

    # Show highest numbered members
    print(f"\nHighest numbered members:")
    sorted_members = sorted(members, key=lambda m: m.number, reverse=True)
    for member in sorted_members[:5]:
        print(f"  #{member.number}: {member.call}")


if __name__ == "__main__":
    asyncio.run(debug_roster())
