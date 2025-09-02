"""Quick demo runner for SKCC awards logic.

Loads a sample ADIF file, synthesizes a minimal roster from SKCC fields
found in the QSOs, and prints a summary of calculated awards.

Usage:
  python scripts/demo_awards.py

This is for local smoke testing; for full correctness, run unit tests or the FastAPI app.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend package is importable (app.*)
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.skcc import (  # noqa: E402
    QSO,
    SKCC_FIELD_RE,
    Member,
    calculate_awards,
    normalize_call,
    parse_adif,
)


def load_adif_text() -> str:
    for candidate in [
        ROOT / "test_adif_sample.adi",
        ROOT / "scripts" / "main.adi",
        ROOT / "main.adi",
    ]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="ignore")
    raise SystemExit("No sample ADIF found (looked for test_adif_sample.adi or main.adi)")


def synthesize_members(qsos: list[QSO]) -> list[Member]:
    members: dict[int, Member] = {}
    for q in qsos:
        if not q.call:
            continue
        if not q.skcc:
            # If no SKCC field, skip; demo roster relies on SKCC field present
            continue
        m = SKCC_FIELD_RE.match(q.skcc.strip().upper())
        if not m:
            continue
        try:
            num = int(m.group("num"))
        except ValueError:
            continue
        suffix = m.group("suffix") or None
        base_call = normalize_call(q.call) or q.call.upper()
        if num not in members:
            members[num] = Member(call=base_call, number=num, suffix=suffix)
    return list(members.values())


def main() -> None:
    text = load_adif_text()
    qsos = parse_adif(text)
    members = synthesize_members(qsos)

    result = calculate_awards(
        qsos,
        members,
        enforce_suffix_rules=True,
        enable_endorsements=True,
        enforce_key_type=False,
    )

    print("=== SKCC Awards Demo ===")
    print(f"QSOs parsed: {len(qsos)} | Synth members: {len(members)}")
    print(f"Unique members worked: {result.unique_members_worked}")
    print(f"Total awards reported: {len(result.awards)}")
    SHOW_N = 10
    for a in result.awards[:SHOW_N]:
        status = "✓" if a.achieved else "…"
        print(f" - {a.name}: {a.current}/{a.required} {status}")
    if len(result.awards) > SHOW_N:
        print(f"(+{len(result.awards)-SHOW_N} more)")

    if result.wac_awards:
        print("\nWAC Highlights:")
        for w in result.wac_awards:
            if w.band is None:  # overall only for brevity
                status = "✓" if w.achieved else "…"
                print(
                    f" - {w.name}: {w.current_continents}/6 {status} "
                    f"[{', '.join(w.continents_worked)}]"
                )


if __name__ == "__main__":
    main()
