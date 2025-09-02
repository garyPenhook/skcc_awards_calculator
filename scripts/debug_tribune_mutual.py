#!/usr/bin/env python3
"""Debug script for Tribune Award calculation with mutual Centurion requirement.

This script analyzes Tribune progress by checking that BOTH parties were
Centurions (or higher) at the time of QSO, which is the official requirement.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add the backend app directory to Python path
backend_path = Path(__file__).parent.parent / "backend" / "app"
sys.path.insert(0, str(backend_path))

from services.skcc import (
    parse_adif,
    fetch_member_roster,
    Member,
    QSO,
    normalize_call,
    generate_call_aliases,
    get_member_status_at_qso_time,
    SKCC_FIELD_RE,
    _qso_timestamp,
)


def parse_adif_files(adif_contents):
    """Parse multiple ADIF file contents and combine QSOs."""
    all_qsos = []
    for content in adif_contents:
        qsos = parse_adif(content)
        all_qsos.extend(qsos)
    return all_qsos


import asyncio


def analyze_tribune_mutual_progress(adif_files, members):
    """Analyze Tribune progress considering mutual Centurion requirement."""

    # Read ADIF file contents
    adif_contents = []
    for file_path in adif_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                adif_contents.append(f.read())
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return

    # Parse ADIF files
    qsos = parse_adif_files(adif_contents)

    # Filter to CW QSOs only
    cw_qsos = [q for q in qsos if q.mode and q.mode.upper() == "CW"]

    print(f"=== TRIBUNE AWARD DEBUG ANALYSIS (MUTUAL CENTURION) ===")
    print()
    print(f"Total QSOs parsed: {len(qsos)}")
    print(f"Total SKCC members in roster: {len(members)}")
    print(f"CW QSOs: {len(cw_qsos)}")
    print()
    print("NOTE: Tribune requires 50 different Centurions/Tribunes/Senators")
    print("      Both parties must have Centurion+ status at time of QSO")
    print()

    # Create lookup structures
    call_to_member = {}
    number_to_member = {}

    for member in members:
        call_to_member[member.call] = member
        number_to_member[member.number] = member

    # Generate call aliases lookup
    aliases = {}
    for member in members:
        for alias in generate_call_aliases(member.call):
            aliases.setdefault(alias, member)
    print(f"Total call sign aliases generated: {len(aliases)}")

    # Find YOUR member record
    your_member = None
    for member in members:
        if member.call == "W4GNS":
            your_member = member
            break

    if not your_member:
        print("ERROR: Could not find W4GNS in member roster!")
        return

    print(
        f"Your SKCC info: {your_member.call} #{your_member.number} {your_member.suffix or 'No suffix'}"
    )
    print()

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

    tribune_qualified = set()
    matched_qsos = 0
    unmatched_calls = set()

    print("=== PROCESSING QSOs CHRONOLOGICALLY (MUTUAL CENTURION CHECK) ===")
    print("Date       Time  Call       SKCC Field  Other@QSO   You@QSO    Member#   Result")
    print("-" * 90)

    for timestamp, q in valid_qsos:
        # Look up the other party
        other_call = normalize_call(q.call)
        member = call_to_member.get(other_call) or aliases.get(other_call)
        numeric_id = None
        result = "NO MATCH"
        status_at_qso = None
        your_status_at_qso = None

        if member:
            # Check if QSO was after their join date
            if member.join_date and timestamp < member.join_date:
                result = f"QSO BEFORE JOIN ({member.join_date})"
            else:
                numeric_id = member.number
                matched_qsos += 1

                # Get OTHER party's status at QSO time
                status_at_qso = get_member_status_at_qso_time(q, member)

                # Get YOUR status at QSO time (create a QSO record for yourself)
                # We need to check if YOU had achieved Centurion by this QSO date
                your_status_at_qso = get_your_status_at_qso_time(your_member, timestamp)

                # Check if BOTH parties qualify for Tribune (C/T/S status)
                other_qualifies = status_at_qso in ["C", "T", "S"]
                you_qualify = your_status_at_qso in ["C", "T", "S"]

                if other_qualifies and you_qualify:
                    if numeric_id not in tribune_qualified:
                        tribune_qualified.add(numeric_id)
                        result = (
                            f"★ TRIBUNE QUALIFIED (Other:{status_at_qso}, You:{your_status_at_qso})"
                        )
                    else:
                        result = f"DUPLICATE (Other:{status_at_qso}, You:{your_status_at_qso})"
                elif other_qualifies and not you_qualify:
                    result = f"YOU NOT QUALIFIED (Other:{status_at_qso}, You:{your_status_at_qso or 'None'})"
                elif not other_qualifies and you_qualify:
                    result = f"OTHER NOT QUALIFIED (Other:{status_at_qso or 'None'}, You:{your_status_at_qso})"
                else:
                    result = f"NEITHER QUALIFIED (Other:{status_at_qso or 'None'}, You:{your_status_at_qso or 'None'})"
        else:
            if other_call:
                result = "NO MATCH"

        if result == "NO MATCH":
            unmatched_calls.add(q.call)

        # Print QSO details
        date_str = q.date[:8] if q.date and len(q.date) >= 8 else "????????"
        time_str = q.time_on[:4] if q.time_on and len(q.time_on) >= 4 else "????"
        skcc_str = (q.skcc or "")[:12].ljust(12)
        member_num = str(numeric_id) if numeric_id else ""

        print(
            f"{date_str} {time_str}  {q.call:<10} {skcc_str} {status_at_qso or '':<10} {your_status_at_qso or '':<10} {member_num:<8} {result}"
        )

    print("-" * 90)
    print(f"Total matched QSOs: {matched_qsos}")
    print(f"Total unmatched calls: {len(unmatched_calls)}")
    print(f"Tribune qualified members (mutual): {len(tribune_qualified)}")
    print()
    print("=== TRIBUNE AWARD SUMMARY ===")
    print(f"Current progress: {len(tribune_qualified)}/50")
    print(f"Achievement status: {'ACHIEVED' if len(tribune_qualified) >= 50 else 'NOT ACHIEVED'}")
    print(f"Percentage: {(len(tribune_qualified) / 50) * 100:.1f}%")
    print()


def get_your_status_at_qso_time(your_member, qso_timestamp):
    """
    Estimate your status at QSO time.
    This is tricky since we don't have historical award data.

    For now, we'll assume:
    - If you're currently a Centurion, we need to estimate when you achieved it
    - You probably achieved Centurion after making 100 CW contacts
    - This is an approximation - ideally we'd have award history
    """

    # If you don't have any suffix, you never achieved Centurion
    if not your_member.suffix:
        return None

    # If you have C/T/S status now, we need to estimate when you got it
    # This is a simplification - in practice, you'd need to track award history
    # For now, let's assume you got Centurion sometime during your log period

    # TODO: This needs better logic based on actual award achievement dates
    # For debugging, let's assume you achieved Centurion after May 20, 2025
    centurion_achievement_date = datetime(
        2025, 6, 1
    )  # Adjust this based on when you think you achieved it

    if qso_timestamp >= centurion_achievement_date:
        return your_member.suffix
    else:
        return None


async def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_tribune_mutual.py <adif_file> [adif_file2 ...]")
        print()
        print("Example:")
        print("  python debug_tribune_mutual.py my_log.adi")
        print("  python debug_tribune_mutual.py log1.adi log2.adi")
        return

    adif_files = sys.argv[1:]

    print("Fetching SKCC roster...")
    members = await fetch_member_roster()
    print(f"Roster loaded: {len(members)} members")
    print()

    print(f"Analyzing ADIF files: {', '.join(adif_files)}")
    analyze_tribune_mutual_progress(adif_files, members)


if __name__ == "__main__":
    asyncio.run(main())
