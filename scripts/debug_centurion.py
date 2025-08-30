#!/usr/bin/env python3
"""Debug script to determine when you achieved Centurion status."""

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

import asyncio

def analyze_centurion_achievement(adif_files, members):
    """Analyze when you might have achieved Centurion status based on QSO count."""
    
    # Read ADIF file contents
    adif_contents = []
    for file_path in adif_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                adif_contents.append(f.read())
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return
    
    # Parse ADIF files
    qsos = parse_adif_files(adif_contents)
    
    # Filter to CW QSOs only
    cw_qsos = [q for q in qsos if q.mode and q.mode.upper() == 'CW']
    
    print(f"=== CENTURION ACHIEVEMENT ANALYSIS ===")
    print()
    print(f"Total QSOs parsed: {len(qsos)}")
    print(f"CW QSOs: {len(cw_qsos)}")
    print()
    
    # Find YOUR member record
    your_member = None
    for member in members:
        if member.call == 'W4GNS':
            your_member = member
            break
    
    if not your_member:
        print("ERROR: Could not find W4GNS in member roster!")
        return
        
    print(f"Your SKCC info: {your_member.call} #{your_member.number} {your_member.suffix or 'No suffix'}")
    print(f"Join date: {your_member.join_date or 'Unknown'}")
    print()
    
    # Create lookup structures for other members
    call_to_member = {}
    aliases = {}
    for member in members:
        call_to_member[member.call] = member
        for alias in generate_call_aliases(member.call):
            aliases.setdefault(alias, member)
    
    # Sort QSOs chronologically
    valid_qsos = []
    for q in cw_qsos:
        if q.date and q.time_on:
            try:
                timestamp = _qso_timestamp(q)
                valid_qsos.append((timestamp, q))
            except:
                continue
    
    valid_qsos.sort()
    
    print("=== ANALYZING QSOs TO ESTIMATE CENTURION ACHIEVEMENT ===")
    print("Note: Centurion requires 100 CW QSOs with SKCC members")
    print()
    
    skcc_contacts = 0
    centurion_achievement_qso = None
    
    for i, (timestamp, q) in enumerate(valid_qsos):
        # Look up the other party
        other_call = normalize_call(q.call)
        member = call_to_member.get(other_call) or aliases.get(other_call)
        
        if member:
            # Check if QSO was after their join date
            if not member.join_date or timestamp >= member.join_date:
                skcc_contacts += 1
                
                # Check if this would be your 100th SKCC contact (Centurion threshold)
                if skcc_contacts == 100 and not centurion_achievement_qso:
                    centurion_achievement_qso = (timestamp, q, i+1)
                    print(f"*** ESTIMATED CENTURION ACHIEVEMENT ***")
                    print(f"QSO #{i+1}: {q.call} on {timestamp.strftime('%Y-%m-%d %H:%M')}")
                    print(f"This would be your 100th SKCC contact")
                    print()
                    break
    
    print(f"Total SKCC contacts in log: {skcc_contacts}")
    
    if centurion_achievement_qso:
        achievement_date, achievement_qso, qso_number = centurion_achievement_qso
        print(f"Estimated Centurion achievement: {achievement_date.strftime('%Y-%m-%d')} (QSO #{qso_number})")
        
        # Now count Tribune-eligible QSOs after Centurion achievement
        tribune_count = 0
        tribune_members = set()
        
        print()
        print("=== TRIBUNE ELIGIBLE QSOs (after Centurion achievement) ===")
        print("NOTE: Tribune requires 50 different Centurions/Tribunes/Senators")
        print("Date       Time  Call       SKCC Field  Other Status  Result")
        print("-" * 70)
        
        for timestamp, q in valid_qsos:
            if timestamp < achievement_date:
                continue  # Skip QSOs before Centurion
                
            other_call = normalize_call(q.call)
            member = call_to_member.get(other_call) or aliases.get(other_call)
            
            if member and (not member.join_date or timestamp >= member.join_date):
                status_at_qso = get_member_status_at_qso_time(q, member)
                if status_at_qso in ['C', 'T', 'S']:
                    if member.number not in tribune_members:
                        tribune_members.add(member.number)
                        tribune_count += 1
                        result = f"★ TRIBUNE #{tribune_count}"
                    else:
                        result = "DUPLICATE"
                    
                    date_str = q.date[:8] if q.date else "????????"
                    time_str = q.time_on[:4] if q.time_on else "????"
                    skcc_str = (q.skcc or "")[:12].ljust(12)
                    
                    print(f"{date_str} {time_str}  {q.call:<10} {skcc_str} {status_at_qso or '':<12} {result}")
        
        print("-" * 70)
        print(f"Tribune eligible contacts: {tribune_count}/50")
        print(f"Tribune achieved: {'YES' if tribune_count >= 50 else 'NO'}")
        
    else:
        print("You haven't reached 100 SKCC contacts yet (Centurion requirement)")
        print(f"Current progress: {skcc_contacts}/100")
        print("Tribune award requires Centurion status first.")
        print("Once Centurion is achieved, Tribune needs 50 different C/T/S contacts.")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_centurion.py <adif_file> [adif_file2 ...]")
        return
    
    adif_files = sys.argv[1:]
    
    print("Fetching SKCC roster...")
    members = await fetch_member_roster()
    print(f"Roster loaded: {len(members)} members")
    print()
    
    analyze_centurion_achievement(adif_files, members)

if __name__ == "__main__":
    asyncio.run(main())
