#!/usr/bin/env python
"""Find the exact HTML structure for our test member numbers."""

import sys
from pathlib import Path
import asyncio
import httpx
import re

# Add backend app to path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

async def find_member_html():
    print("=== Finding HTML structure for test members ===")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("https://www.skccgroup.com/membership_data/membership_roster.php")
        html_content = response.text
    
    test_numbers = ["660", "1395", "13613", "24472", "25995"]
    
    for num in test_numbers:
        print(f"\n=== Searching for member {num} ===")
        
        # Try different search patterns
        patterns = [
            rf'\b{num}\b',  # Word boundary
            rf'>{num}<',    # In HTML tags
            rf'#{num}',     # With hash
            num,            # Simple substring
        ]
        
        for pattern_name, pattern in [
            ("word boundary", patterns[0]),
            ("HTML tags", patterns[1]), 
            ("with hash", patterns[2]),
            ("substring", patterns[3])
        ]:
            if pattern_name == "substring":
                matches = []
                start = 0
                while True:
                    pos = html_content.find(pattern, start)
                    if pos == -1:
                        break
                    match_obj = type('Match', (), {
                        'start': lambda p=pos: p, 
                        'end': lambda p=pos, l=len(pattern): p + l
                    })()
                    matches.append(match_obj)
                    start = pos + 1
            else:
                matches = list(re.finditer(pattern, html_content))
            
            print(f"  {pattern_name}: {len(matches)} matches")
            
            if matches and len(matches) < 10:  # Show details for reasonable number of matches
                for i, match in enumerate(matches[:3]):  # Show first 3
                    start = max(0, match.start() - 100)
                    end = min(len(html_content), match.end() + 100)
                    context = html_content[start:end].replace('\n', '\\n').replace('\t', '\\t')
                    print(f"    Match {i+1}: ...{context}...")
        
        print("---")

if __name__ == "__main__":
    asyncio.run(find_member_html())
