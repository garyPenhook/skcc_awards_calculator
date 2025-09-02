#!/usr/bin/env python
"""Simple search to find where our test numbers appear in the HTML."""

import sys
from pathlib import Path
import asyncio
import httpx

# Add backend app to path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))


async def simple_search():
    print("=== Simple search for test numbers ===")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://www.skccgroup.com/membership_data/membership_roster.php"
        )
        html_content = response.text

    test_numbers = ["660", "1395", "13613"]

    for num in test_numbers:
        print(f"\n=== Looking for {num} ===")

        # Find all positions where this number appears
        positions = []
        start = 0
        while True:
            pos = html_content.find(num, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1

        print(f"Found {len(positions)} occurrences")

        # Show first few contexts
        for i, pos in enumerate(positions[:3]):
            start_ctx = max(0, pos - 50)
            end_ctx = min(len(html_content), pos + len(num) + 50)
            context = html_content[start_ctx:end_ctx]
            # Clean up for display
            context = context.replace("\n", " ").replace("\t", " ")
            context = " ".join(context.split())  # Normalize whitespace

            print(f"  {i+1}: ...{context}...")


if __name__ == "__main__":
    asyncio.run(simple_search())
