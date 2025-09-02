#!/usr/bin/env python
"""CLI tool to evaluate SKCC award progress from one or more ADIF files.

Examples:
  # Online (fetch live roster)
  python scripts/awards_check.py --adif log1.adi log2.adi

  # Offline with mock members
  python scripts/awards_check.py --adif log.adi --mock-members K1ABC=10 WA9XYZ=11

  # Offline with CSV roster (columns: number,call)
  python scripts/awards_check.py --adif log.adi --members-csv roster.csv
"""
from __future__ import annotations
import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import List

# Allow running from repo root
sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "app"))

from services.skcc import (
    fetch_member_roster,
    parse_adif,
    calculate_awards,
    Member,
)


def parse_adif_files(adif_contents: List[str]):
    """Parse multiple ADIF file contents and combine QSOs."""
    all_qsos = []
    for content in adif_contents:
        qsos = parse_adif(content)
        all_qsos.extend(qsos)
    return all_qsos


def load_members_from_csv(path: Path) -> List[Member]:
    members: List[Member] = []
    with path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            try:
                number = int(row[0].strip())
                call = row[1].strip().upper()
            except (ValueError, IndexError):
                continue
            members.append(Member(call=call, number=number))
    return members


async def main():
    ap = argparse.ArgumentParser(description="Check SKCC award progress from ADIF files.")
    ap.add_argument("--adif", nargs="+", required=True, help="One or more ADIF files to parse")
    ap.add_argument("--roster-url", default=None, help="Override roster URL")
    ap.add_argument("--members-csv", type=Path, help="CSV file with columns: number,call")
    ap.add_argument(
        "--mock-members",
        nargs="*",
        help="Inline mock members CALL=NUMBER ... for offline use",
    )
    ap.add_argument("--json", action="store_true", help="Output raw JSON only")
    args = ap.parse_args()

    # Load ADIF contents
    adif_contents: List[str] = []
    for p in args.adif:
        path = Path(p)
        if not path.exists():
            ap.error(f"ADIF file not found: {p}")
        adif_contents.append(path.read_text(encoding="utf-8", errors="ignore"))

    qsos = parse_adif_files(adif_contents)

    # Obtain members
    members: List[Member] = []
    if args.members_csv:
        members = load_members_from_csv(args.members_csv)
    elif args.mock_members:
        for token in args.mock_members:
            if "=" not in token:
                continue
            call, num = token.split("=", 1)
            try:
                members.append(Member(call=call.upper(), number=int(num)))
            except ValueError:
                continue
    else:
        members = (
            await fetch_member_roster(args.roster_url)
            if args.roster_url
            else await fetch_member_roster()
        )

    result = calculate_awards(qsos, members)  # CW-only enforced in service (default)

    output = {
        "unique_members_worked": result.unique_members_worked,
        "total_qsos": result.total_qsos,
        "total_cw_qsos": result.total_cw_qsos,
        "matched_qsos": result.matched_qsos,
        "unmatched_calls": result.unmatched_calls,
        "thresholds_used": [{"name": n, "required": r} for n, r in result.thresholds_used],
        "awards": [
            {
                "name": a.name,
                "required": a.required,
                "current": a.current,
                "achieved": a.achieved,
            }
            for a in result.awards
        ],
        "endorsements": [
            {
                "award": e.award,
                "category": e.category,
                "value": e.value,
                "required": e.required,
                "current": e.current,
                "achieved": e.achieved,
            }
            for e in result.endorsements
        ],
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"Unique SKCC members worked: {output['unique_members_worked']}")
        print("Mode policy: CW-only QSOs counted.")
        print(
            f"QSOs: total={output['total_qsos']} CW={output['total_cw_qsos']} matched={output['matched_qsos']} unmatched={len(output['unmatched_calls'])}"
        )
        if output["unmatched_calls"]:
            print("Unmatched calls (top 10):", ", ".join(output["unmatched_calls"][:10]))
        print("Thresholds:")
        for t in output["thresholds_used"]:
            print(f" - {t['name']}: {t['required']}")
        print("Awards:")
        for a in output["awards"]:
            status = "ACHIEVED" if a["achieved"] else "in progress"
            print(f" - {a['name']}: {a['current']}/{a['required']} ({status})")
        if output["endorsements"]:
            print("Endorsements (band/mode):")
            for e in output["endorsements"]:
                print(
                    f"   * {e['award']} {e['category']} {e['value']}: {e['current']}/{e['required']}"
                )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
