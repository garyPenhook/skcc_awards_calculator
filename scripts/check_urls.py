#!/usr/bin/env python
"""Check the actual SKCC roster URLs and content to find the real issue."""

import sys
from pathlib import Path
import asyncio
import httpx

# Add backend app to path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))


async def check_skcc_urls():
    print("=== Checking SKCC Website URLs ===")

    # Test different possible URLs for the roster
    test_urls = [
        "https://www.skccgroup.com/membership_data/membership_roster.php",
        "https://www.skccgroup.com/membership_data/membership_listing.php",
        "https://www.skccgroup.com/membership_data/membership.php",
        "https://www.skccgroup.com/membership_data/roster.php",
        "https://www.skccgroup.com/membership_data/",
        "https://www.skccgroup.com/membership_data/roster.txt",
        "https://www.skccgroup.com/membership_data/membership.txt",
        "https://www.skccgroup.com/membership_data/roster.csv",
        "https://www.skccgroup.com/awards/membership_roster.php",
        "https://skccgroup.com/membership_data/membership_roster.php",
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for url in test_urls:
            try:
                print(f"\nTesting: {url}")
                response = await client.get(url)
                print(f"  Status: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('content-type', 'unknown')}")
                print(f"  Content-Length: {len(response.text)}")

                # Look for specific member numbers in the content
                content = response.text.lower()
                test_numbers = ["660", "1395", "13613", "24472", "25995"]
                found = []
                for num in test_numbers:
                    if num in content:
                        found.append(num)

                if found:
                    print(f"  *** FOUND test numbers: {found}")
                else:
                    print(f"  No test numbers found")

                # Show first few lines of content
                lines = response.text.split("\n")[:5]
                print(f"  First 5 lines:")
                for i, line in enumerate(lines):
                    print(f"    {i+1}: {line[:80]}")

            except Exception as e:
                print(f"  Error: {e}")


if __name__ == "__main__":
    asyncio.run(check_skcc_urls())
