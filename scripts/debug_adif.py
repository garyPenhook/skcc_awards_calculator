#!/usr/bin/env python
"""Debug ADIF parsing to see why only 9 of 100 contacts are found."""

import sys
from pathlib import Path

# Add backend app to path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
if str(BACKEND_APP) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP))

from services.skcc import parse_adif, calculate_awards, fetch_member_roster
import asyncio

async def debug_adif_parsing():
    adif_file = Path(__file__).parent / "main.adi"
    
    with open(adif_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"ADIF file size: {len(content)} characters")
    print(f"ADIF file lines: {content.count(chr(10))} lines")
    
    # Count EOR markers
    eor_count = content.lower().count("<eor>")
    print(f"EOR markers found: {eor_count}")
    
    # Parse the ADIF
    qsos = parse_adif(content)
    print(f"QSOs parsed: {len(qsos)}")
    
    # Show first few QSOs
    for i, qso in enumerate(qsos[:5]):
        print(f"QSO {i+1}: Call={qso.call}, Date={qso.date}, Band={qso.band}, SKCC={qso.skcc}")
    
    # Check for QSOs without calls
    qsos_without_calls = [qso for qso in qsos if not qso.call]
    print(f"QSOs without calls: {len(qsos_without_calls)}")
    
    # Look for patterns in the file
    lines = content.split('\n')
    call_lines = [line for line in lines if '<CALL:' in line.upper()]
    print(f"Lines with CALL field: {len(call_lines)}")
    
    # Show some call lines
    for i, line in enumerate(call_lines[:5]):
        print(f"Call line {i+1}: {line.strip()}")
    
    # Now test award calculation
    print("\n--- Testing Award Calculation ---")
    try:
        # Fetch roster
        print("Fetching member roster...")
        members = await fetch_member_roster()
        print(f"Roster members: {len(members)}")
        
        # Calculate awards
        print("Calculating awards...")
        awards = calculate_awards(qsos, members)
        print(f"Total QSOs: {awards.total_qsos}")
        print(f"Matched QSOs: {awards.matched_qsos}")
        print(f"Unique members worked: {awards.unique_members_worked}")
        print(f"Total CW QSOs: {awards.total_cw_qsos}")
        print(f"Unmatched calls: {len(awards.unmatched_calls)}")
        
        # Show award progress
        print("Award progress (legacy counting - all members count):")
        for award in awards.awards:
            desc = f" - {award.description}" if award.description else ""
            print(f"  {award.name}: {award.current}/{award.required} ({'ACHIEVED' if award.achieved else 'in progress'}){desc}")
            
        # Now test with suffix enforcement enabled (proper SKCC rules)
        print("\n--- Testing with SKCC suffix rules enforced ---")
        awards_with_suffix = calculate_awards(qsos, members, enforce_suffix_rules=True)
        print(f"Total QSOs: {awards_with_suffix.total_qsos}")
        print(f"Matched QSOs: {awards_with_suffix.matched_qsos}")
        print(f"Unique members worked: {awards_with_suffix.unique_members_worked}")
        
        # Show award progress with suffix rules enforced
        print("Award progress with proper SKCC suffix enforcement:")
        for award in awards_with_suffix.awards:
            desc = f" - {award.description}" if award.description else ""
            print(f"  {award.name}: {award.current}/{award.required} ({'ACHIEVED' if award.achieved else 'in progress'}){desc}")
            
        # Show some unmatched calls
        if awards.unmatched_calls:
            print(f"\nFirst 10 unmatched calls: {awards.unmatched_calls[:10]}")
            
        # Show QSO-time status analysis (accurate from SKCC Logger)
        print(f"\nQSO-time status analysis (from SKCC field in log):")
        member_by_call = {}
        for member in members:
            from services.skcc import generate_call_aliases
            for alias in generate_call_aliases(member.call):
                member_by_call.setdefault(alias, member)
        
        # Look at first few QSOs to show QSO-time vs current status
        print("Sample QSOs showing status at QSO time vs current roster status:")
        for i, qso in enumerate(qsos[:6]):
            if qso.call in member_by_call:
                member = member_by_call[qso.call]
                current_suffix = member.suffix or 'None'
                current_desc = {'C': 'Centurion', 'T': 'Tribune', 'S': 'Senator', 'None': 'No award'}.get(current_suffix, current_suffix)
                
                # Get QSO-time status from SKCC field
                qso_time_suffix = None
                if qso.skcc:
                    import re
                    match = re.match(r'(\d+)([A-Z]*)', qso.skcc.strip().upper())
                    if match:
                        qso_time_suffix = match.group(2) if match.group(2) else None
                
                qso_time_desc = {'C': 'Centurion', 'T': 'Tribune', 'S': 'Senator', None: 'No award'}.get(qso_time_suffix, 'Unknown')
                
                # Determine qualification for awards
                tribune_qualified = qso_time_suffix in ['C', 'T', 'S'] if qso_time_suffix else False
                senator_qualified = qso_time_suffix in ['T', 'S'] if qso_time_suffix else False
                
                print(f"  {qso.call}: QSO on {qso.date}")
                print(f"    SKCC field: {qso.skcc}")
                print(f"    Status at QSO time: {qso_time_desc}")
                print(f"    Current roster status: {current_desc}")
                print(f"    Tribune credit: {'✓' if tribune_qualified else '✗'}")
                print(f"    Senator credit: {'✓' if senator_qualified else '✗'}")
                print()
        
        print("This is the CORRECT approach - using the member's award status")
        print("as it was recorded at the time of QSO, not guessing from current roster!")
            
        # Show some unmatched calls
        if awards.unmatched_calls:
            print(f"\nFirst 10 unmatched calls: {awards.unmatched_calls[:10]}")
            
        # Test specific call signs
        print("\n--- Testing specific call lookups ---")
        test_calls = ['KA3LOC', 'IZ0FBJ', 'NJ8L', 'WX7V', 'K8JD', 'AA4NO']
        
        # Build member lookup
        member_by_call = {}
        for member in members:
            from services.skcc import generate_call_aliases
            for alias in generate_call_aliases(member.call):
                member_by_call.setdefault(alias, member)
        
        for call in test_calls:
            if call in member_by_call:
                member = member_by_call[call]
                suffix_info = f" (suffix: {member.suffix})" if member.suffix else " (no suffix)"
                print(f"{call} -> FOUND: {member.call} (#{member.number}){suffix_info}")
            else:
                print(f"{call} -> NOT FOUND in roster")
                
        # Check if SKCC numbers match
        print("\n--- Checking SKCC number matches ---")
        for qso in qsos[:10]:
            if qso.skcc:
                # Extract number from SKCC field
                import re
                skcc_match = re.match(r'^(\d+)[A-Z]*$', qso.skcc.strip())
                if skcc_match:
                    skcc_num = int(skcc_match.group(1))
                    # Check if this number is in the roster
                    number_found = any(m.number == skcc_num for m in members)
                    print(f"{qso.call} SKCC:{qso.skcc} -> Number {skcc_num} {'FOUND' if number_found else 'NOT FOUND'} in roster")
                    
        # Show some roster samples
        print("\n--- Sample roster entries ---")
        for i, member in enumerate(members[:10]):
            print(f"Member {i+1}: {member.call} (#{member.number})")
            
        # Check number ranges
        numbers = [m.number for m in members]
        print(f"\nRoster number range: {min(numbers)} to {max(numbers)}")
        print(f"Numbers > 25000: {len([n for n in numbers if n > 25000])}")
        print(f"Numbers > 29000: {len([n for n in numbers if n > 29000])}")
            
    except Exception as e:
        print(f"Error in award calculation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_adif_parsing())
