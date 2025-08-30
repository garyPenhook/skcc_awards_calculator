#!/usr/bin/env python3
"""Debug script for Tribune Award calculation.

This script will help analyze your Tribune award progress by showing:
1. Which SKCC members you've contacted who had C/T/S status at QSO time
2. The specific QSO details and their award status at that time
3. Any issues with member status validation
"""

import sys
from pathlib import Path
from datetime import datetime

# Add the backend app directory to Python path
backend_path = Path(__file__).parent.parent / 'backend' / 'app'
sys.path.insert(0, str(backend_path))

from services.skcc import (
    parse_adif, fetch_member_roster, Member, QSO,
    normalize_call, generate_call_aliases, get_member_status_at_qso_time,
    SKCC_FIELD_RE, _qso_timestamp
)

def parse_adif_files(adif_contents):
    """Parse multiple ADIF file contents and combine QSOs."""
    all_qsos = []
    for content in adif_contents:
        qsos = parse_adif(content)
        all_qsos.extend(qsos)
    return all_qsos

def analyze_tribune_progress(adif_files, members):
    """Analyze Tribune award progress in detail."""
    
    print("=== TRIBUNE AWARD DEBUG ANALYSIS ===\n")
    
    # Parse ADIF files
    if isinstance(adif_files, list):
        adif_contents = [Path(f).read_text(encoding="utf-8", errors="ignore") for f in adif_files]
    else:
        adif_contents = [Path(adif_files).read_text(encoding="utf-8", errors="ignore")]
    
    qsos = parse_adif_files(adif_contents)
    print(f"Total QSOs parsed: {len(qsos)}")
    
    # Build member lookup
    member_by_call = {}
    number_to_member = {}
    for member in members:
        number_to_member[member.number] = member
        for alias in generate_call_aliases(member.call):
            member_by_call.setdefault(alias, member)
    
    print(f"Total SKCC members in roster: {len(members)}")
    print(f"Total call sign aliases generated: {len(member_by_call)}")
    
    # Filter CW QSOs only
    cw_qsos = [q for q in qsos if q.mode and q.mode.upper() == "CW"]
    print(f"CW QSOs: {len(cw_qsos)}")
    
    # Sort chronologically
    chronological = sorted(cw_qsos, key=_qso_timestamp)
    
    # Track Tribune qualifications
    tribune_qualified = {}  # member_id -> (qso, status_at_time, member)
    matched_qsos = 0
    unmatched_calls = set()
    
    print("\n=== PROCESSING QSOs CHRONOLOGICALLY ===")
    print("Date       Time  Call       SKCC Field  Status@QSO  Member#   Result")
    print("-" * 80)
    
    for q in chronological:
        if not q.call:
            continue
            
        # Try to match member
        normalized_call = normalize_call(q.call)
        member = member_by_call.get(normalized_call)
        numeric_id = None
        status_at_qso = "?"
        result = "NO MATCH"
        
        if member:
            # Check join date
            if member.join_date and q.date and q.date < member.join_date:
                result = f"QSO BEFORE JOIN ({member.join_date})"
            else:
                numeric_id = member.number
                matched_qsos += 1
                
                # Get member status at QSO time
                status_at_qso = get_member_status_at_qso_time(q, member)
                
                # Check if qualifies for Tribune (C/T/S status)
                if status_at_qso in ['C', 'T', 'S']:
                    if numeric_id not in tribune_qualified:
                        tribune_qualified[numeric_id] = (q, status_at_qso, member)
                        result = f"★ TRIBUNE QUALIFIED ({status_at_qso})"
                    else:
                        result = f"DUPLICATE ({status_at_qso})"
                else:
                    result = f"NO STATUS ({status_at_qso})"
        else:
            # Try SKCC field if call didn't match
            if q.skcc:
                msk = SKCC_FIELD_RE.match(q.skcc.strip().upper())
                if msk:
                    candidate = int(msk.group("num"))
                    if candidate in number_to_member:
                        member = number_to_member[candidate]
                        if not (member.join_date and q.date and q.date < member.join_date):
                            numeric_id = candidate
                            matched_qsos += 1
                            status_at_qso = get_member_status_at_qso_time(member, q)
                            
                            if status_at_qso in ['C', 'T', 'S']:
                                if numeric_id not in tribune_qualified:
                                    tribune_qualified[numeric_id] = (q, status_at_qso, member)
                                    result = f"★ TRIBUNE QUALIFIED ({status_at_qso}) via SKCC#"
                                else:
                                    result = f"DUPLICATE ({status_at_qso}) via SKCC#"
                            else:
                                result = f"NO STATUS ({status_at_qso}) via SKCC#"
                    else:
                        result = f"UNKNOWN SKCC# {candidate}"
            
            if result == "NO MATCH":
                unmatched_calls.add(q.call)
        
        # Print QSO details
        date_str = q.date[:8] if q.date and len(q.date) >= 8 else "????????"
        time_str = q.time_on[:4] if q.time_on and len(q.time_on) >= 4 else "????"
        skcc_str = (q.skcc or "")[:12].ljust(12)
        member_num = str(numeric_id) if numeric_id else ""
        
        print(f"{date_str} {time_str}  {q.call:<10} {skcc_str} {status_at_qso or '':<10} {member_num:<8} {result}")
    
    print("-" * 80)
    print(f"Total matched QSOs: {matched_qsos}")
    print(f"Total unmatched calls: {len(unmatched_calls)}")
    print(f"Tribune qualified members: {len(tribune_qualified)}")
    
    print(f"\n=== TRIBUNE AWARD SUMMARY ===")
    print(f"Current progress: {len(tribune_qualified)}/50")
    print(f"Achievement status: {'ACHIEVED' if len(tribune_qualified) >= 50 else 'NOT ACHIEVED'}")
    print(f"Percentage: {len(tribune_qualified)/50*100:.1f}%")

    if len(tribune_qualified) > 0:
        print(f"\n=== TRIBUNE QUALIFIED MEMBERS ({len(tribune_qualified)}) ===")
        print("Member#   Call       Date       Status  SKCC Field")
        print("-" * 50)
        
        # Sort by QSO date
        sorted_qualified = sorted(tribune_qualified.items(), 
                                key=lambda x: x[1][0].date or "99999999")
        
        for member_id, (qso, status, member) in sorted_qualified:
            date_str = qso.date[:8] if qso.date and len(qso.date) >= 8 else "????????"
            skcc_field = (qso.skcc or "")[:12]
            print(f"{member_id:<8} {member.call:<10} {date_str} {status:<6} {skcc_field}")
    
    if len(unmatched_calls) > 0:
        print(f"\n=== UNMATCHED CALLS ({len(unmatched_calls)}) ===")
        for call in sorted(unmatched_calls):
            print(f"  {call}")
        print("\nNote: These calls were not found in the SKCC roster.")
        print("They might be:")
        print("- Non-SKCC members")
        print("- Call signs with different formatting (portable, etc.)")
        print("- Members who joined after your QSO")
        print("- Expired/inactive members not in current roster")

def main():
    """Main function to run Tribune analysis."""
    
    if len(sys.argv) < 2:
        print("Usage: python debug_tribune.py <adif_file> [adif_file2 ...]")
        print("\nExample:")
        print("  python debug_tribune.py my_log.adi")
        print("  python debug_tribune.py log1.adi log2.adi")
        sys.exit(1)
    
    adif_files = sys.argv[1:]
    
    # Verify files exist
    for f in adif_files:
        if not Path(f).exists():
            print(f"Error: File {f} not found")
            sys.exit(1)
    
    print("Fetching SKCC roster...")
    try:
        members = asyncio.run(fetch_member_roster())
        print(f"Roster loaded: {len(members)} members")
    except Exception as e:
        print(f"Failed to fetch roster: {e}")
        sys.exit(1)
    
    print(f"\nAnalyzing ADIF files: {', '.join(adif_files)}")
    analyze_tribune_progress(adif_files, members)

if __name__ == "__main__":
    main()
