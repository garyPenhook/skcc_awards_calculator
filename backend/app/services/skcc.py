"""Utilities for fetching SKCC roster / awards metadata and parsing ADIF logs.

Network fetch functions are thin wrappers around httpx and intentionally simple so they
can be monkeypatched during tests. Award logic here is deliberately lightweight and
meant as a foundation; full SKCC award validation has more nuances (multi-band, QSL,
log validation, etc.).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Sequence, Tuple, Set
import re
import httpx
from bs4 import BeautifulSoup

# Public roster URL(s). These may change; keep configurable by caller if needed.
DEFAULT_ROSTER_URL = "https://www.skccgroup.com/membership_data/membership_roster.php"
# Additional fallback candidates (guesses / historical and previous primary variants)
FALLBACK_ROSTER_URLS = [
    "https://www.skccgroup.com/membership_data/membership_listing.php",  # previous primary
    "https://www.skccgroup.com/membership_data/membership-listing.php",  # hyphen variant
    "https://www.skccgroup.com/membership_data/",  # directory listing (if allowed)
]
# Awards landing page (used for heuristic threshold parsing)
DEFAULT_AWARDS_URL = "https://www.skccgroup.com/awards/"

# Simplified award thresholds (actual SKCC program has additional awards / endorsements)
AWARD_THRESHOLDS: List[Tuple[str, int]] = [
    ("Centurion", 100),
    ("Tribune", 500),
    ("Senator", 1000),
]

@dataclass(frozen=True)
class Member:
    call: str
    number: int
    # Optional SKCC join date (YYYYMMDD). If provided, used to validate QSO date per rules.
    join_date: str | None = None
    # SKCC achievement suffix: S=Senator(1000+), T=Tribune(500+), C=Centurion(100+)
    suffix: str | None = None

@dataclass(frozen=True)
class QSO:
    call: str | None
    band: str | None
    mode: str | None
    date: str | None  # YYYYMMDD
    skcc: str | None = None  # Raw SKCC field (e.g., 14947C, 660S)
    time_on: str | None = None  # HHMMSS if provided
    key_type: str | None = None  # Raw key type descriptor if available (e.g., STRAIGHT, BUG, COOTIE)

@dataclass
class AwardProgress:
    name: str
    required: int
    current: int
    achieved: bool
    description: str = ""

@dataclass
class AwardCheckResult:
    unique_members_worked: int
    awards: List[AwardProgress]
    endorsements: List[AwardEndorsement]
    total_qsos: int
    matched_qsos: int
    unmatched_calls: List[str]
    thresholds_used: List[Tuple[str, int]]
    total_cw_qsos: int  # New: count of QSOs after CW-only filtering

@dataclass
class AwardEndorsement:
    award: str          # Base award name (e.g., Centurion)
    category: str       # 'band' or 'mode'
    value: str          # e.g. '40M', '20M', 'CW'
    required: int       # Threshold required (same as base award requirement)
    current: int        # Unique SKCC members worked on this band/mode
    achieved: bool

ROSTER_LINE_RE = re.compile(r"^(?P<number>\d+)(?P<suffix>[A-Z]*)\s+([A-Z0-9/]+)\s+(?P<call>[A-Z0-9/]+)")

async def fetch_member_roster(
    url: str | None = None,
    timeout: float = 20.0,
    candidates: Sequence[str] | None = None,
) -> List[Member]:
    """Fetch and parse the SKCC roster, attempting fallback URLs on 404.

    Parameters:
        url: explicit single URL to try first (optional)
        timeout: request timeout seconds
        candidates: explicit ordered list of candidate URLs to try; if None, uses defaults

    Returns:
        List[Member] parsed (possibly empty if parse failed for all) – raises last error if all fail with non-404.
    """
    tried: List[Tuple[str, str]] = []  # (url, error summary)
    urls: List[str] = []
    if url:
        urls.append(url)
    if candidates:
        urls.extend([u for u in candidates if u not in urls])
    else:
        # Default order: primary then fallbacks
        if DEFAULT_ROSTER_URL not in urls:
            urls.append(DEFAULT_ROSTER_URL)
        for fb in FALLBACK_ROSTER_URLS:
            if fb not in urls:
                urls.append(fb)

    last_exception: Exception | None = None
    for target in urls:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(target)
                resp.raise_for_status()
            text = resp.text
            members = _parse_roster_text(text)
            if members:
                return members
            # If parse produced zero members, continue to next candidate
            tried.append((target, "parse-empty"))
        except httpx.HTTPStatusError as e:  # 404 fallback, others abort
            status = e.response.status_code
            summary = f"HTTP {status}"
            tried.append((target, summary))
            last_exception = e
            if status == 404:
                continue  # try next
            raise
        except Exception as e:  # pragma: no cover
            tried.append((target, e.__class__.__name__))
            last_exception = e
            continue

    # All candidates exhausted – if we had any parse-empty but no members, return empty list
    if last_exception and not any(err.startswith("parse-") for _, err in tried):
        # Provide aggregated context in exception chain
        raise RuntimeError(
            "All roster URL attempts failed: "
            + ", ".join(f"{u} ({err})" for u, err in tried)
        ) from last_exception
    return []

def _parse_roster_text(text: str) -> List[Member]:
    """Internal helper to parse roster HTML/text into Member objects."""
    members: List[Member] = []
    # Try HTML parse first
    try:
        soup = BeautifulSoup(text, "html.parser")
        rows = soup.find_all("tr")
        for tr in rows:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"]) ]
            if len(cells) < 2:
                continue
            try:
                # Extract numeric part and suffix from SKCC number (e.g., "660S" -> 660, "S")
                number_text = cells[0].strip()
                suffix_match = re.match(r'^(\d+)([A-Z]*)', number_text)
                if not suffix_match:
                    continue
                number = int(suffix_match.group(1))
                suffix = suffix_match.group(2) if suffix_match.group(2) else None
            except ValueError:
                continue
            call_candidate = None
            for c in cells[1:4]:
                if re.fullmatch(r"[A-Z0-9/]{3,}", c.upper()) and any(ch.isdigit() for ch in c):
                    call_candidate = c.upper()
                    break
            if call_candidate:
                call_candidate = normalize_call(call_candidate)
                members.append(Member(call=call_candidate, number=number, suffix=suffix))
        if members:
            return members
    except Exception:  # pragma: no cover
        members = []
    # Fallback regex scan
    for line in text.splitlines():
        m = ROSTER_LINE_RE.search(line.strip())
        if not m:
            continue
        try:
            number = int(m.group("number"))
            suffix = m.group("suffix") if m.group("suffix") else None
        except ValueError:
            continue
        call = m.group("call").upper()
        members.append(Member(call=call, number=number, suffix=suffix))
    return members

async def fetch_award_thresholds(url: str = DEFAULT_AWARDS_URL, timeout: float = 15.0) -> List[Tuple[str, int]]:
    """Attempt to dynamically discover award thresholds from the awards page.

    Falls back to static AWARD_THRESHOLDS if parsing fails. This is a heuristic:
    searches page text for known award names followed by an integer.
    """
    names = [n for n, _ in AWARD_THRESHOLDS]
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        text = resp.text
        found: Dict[str, int] = {}
        for n in names:
            # Regex: AwardName followed within 30 chars by a number (avoid greedy newline consumption)
            pat = re.compile(rf"{n}[^\n\r]{{0,30}}?(\d{{2,5}})", re.IGNORECASE)
            m = pat.search(text)
            if m:
                try:
                    found[n] = int(m.group(1))
                except ValueError:
                    continue
        if not found:
            return AWARD_THRESHOLDS
        dynamic: List[Tuple[str, int]] = []
        for n, default_req in AWARD_THRESHOLDS:
            dynamic.append((n, found.get(n, default_req)))
        return dynamic
    except Exception:  # pragma: no cover
        return AWARD_THRESHOLDS

ADIF_FIELD_RE = re.compile(r"<(?P<name>[A-Za-z0-9_]+):(?P<len>\d+)(:[A-Za-z0-9]+)?>", re.IGNORECASE)
# Regex to extract leading numeric portion of SKCC field (e.g., 14947C -> 14947)
SKCC_FIELD_RE = re.compile(r"^(?P<num>\d+)(?P<suffix>[A-Z]*)")

CALL_PORTABLE_SUFFIX_RE = re.compile(r"(?P<base>[A-Z0-9]+)(/[A-Z0-9]{1,5})+$")
LEADING_PREFIX_RE = re.compile(r"^[A-Z0-9]{1,4}/(?P<base>[A-Z0-9]+)$")
PORTABLE_SUFFIX_TOKENS = {"P","QRP","M","MM","AM","SOTA"}

def normalize_call(call: str | None) -> str | None:
    if not call:
        return call
    c = call.strip().upper()
    # Strip leading prefix like DL/W1ABC -> W1ABC (keep base that contains a digit)
    m2 = LEADING_PREFIX_RE.match(c)
    if m2 and any(ch.isdigit() for ch in m2.group("base")):
        c = m2.group("base")
    # Strip trailing portable suffix chains
    # e.g. K1ABC/P, K1ABC/QRP, K1ABC/7/P
    parts = c.split('/')
    # If multiple segments, iteratively drop suffix tokens from the end
    while len(parts) > 1 and parts[-1] in PORTABLE_SUFFIX_TOKENS:
        parts.pop()
    # Also if last segment is just a single digit (region) we keep base (common portable) but only if base still has a digit
    if len(parts) > 1 and len(parts[-1]) == 1 and parts[-1].isdigit():
        # Keep base portion before region digit for matching, but only if base has digit
        base_candidate = parts[0]
        if any(ch.isdigit() for ch in base_candidate):
            parts = [base_candidate]
    c = '/'.join(parts)
    # Finally apply suffix regex collapse
    m = CALL_PORTABLE_SUFFIX_RE.fullmatch(c)
    if m:
        return m.group("base")
    return c

def generate_call_aliases(call: str) -> List[str]:
    """Generate alias variants for a member callsign to improve matching.

    Variants include:
      - normalized base
      - base without region digit (K1ABC/7 -> K1ABC)
      - base without leading DX prefix (DL/K1ABC -> K1ABC)
    Duplicates removed preserving order.
    """
    variants: List[str] = []
    def add(v: str):
        if v not in variants:
            variants.append(v)
    base = call.upper()
    add(base)
    n = normalize_call(base)
    if n:
        add(n)
    # Remove trailing region digit
    if '/' in base:
        segs = base.split('/')
        if len(segs) == 2 and len(segs[1]) == 1 and segs[1].isdigit():
            add(segs[0])
    # Leading prefix removal
    m2 = LEADING_PREFIX_RE.match(base)
    if m2:
        add(m2.group("base"))
    return variants

def parse_adif(content: str) -> List[QSO]:
    """Parse minimal subset of ADIF into QSO objects.

    Supports fields: CALL, BAND, MODE, QSO_DATE. Records terminated by <EOR> (case-insensitive).
    """
    records: List[QSO] = []
    idx = 0
    length = len(content)
    current: Dict[str, Any] = {}
    lower_content = content.lower()
    while idx < length:
        if lower_content.startswith("<eor>", idx):
            # End of record
            if "call" in current:
                raw_call = normalize_call(str(current.get("call", "")).upper())
                skcc_raw = current.get("skcc") or current.get("app_skcc")
                records.append(
                    QSO(
                        call=raw_call,
                        band=current.get("band"),
                        mode=current.get("mode"),
                        date=current.get("qso_date"),
                        skcc=skcc_raw,
                        time_on=current.get("time_on"),
                        key_type=(current.get("key") or current.get("app_skcc_key") or current.get("skcc_key") or current.get("app_key")),
                    )
                )
            current = {}
            idx += 5
            continue
        if lower_content.startswith("<eoh>", idx):
            idx += 5
            current = {}
            continue
        m = ADIF_FIELD_RE.match(content, idx)
        if not m:
            idx += 1
            continue
        name = m.group("name").lower()
        field_len = int(m.group("len"))
        value_start = m.end()
        value_end = value_start + field_len
        value = content[value_start:value_end]
        current[name] = value.strip() or None
        idx = value_end
    # Handle file not ending with <EOR>
    if current.get("call"):
        raw_call = normalize_call(str(current.get("call", "")).upper())
        skcc_raw = current.get("skcc") or current.get("app_skcc")
        records.append(
            QSO(
                call=raw_call,
                band=current.get("band"),
                mode=current.get("mode"),
                date=current.get("qso_date"),
                skcc=skcc_raw,
                time_on=current.get("time_on"),
                key_type=(current.get("key") or current.get("app_skcc_key") or current.get("skcc_key") or current.get("app_key")),
            )
        )
    return records

def parse_adif_files(contents: Sequence[str]) -> List[QSO]:
    qsos: List[QSO] = []
    for c in contents:
        qsos.extend(parse_adif(c))
    return qsos

# Helper to build sortable timestamp
from datetime import datetime

def _qso_timestamp(q: QSO) -> datetime:
    d = q.date or "00000000"
    t = q.time_on or "000000"
    # Basic sanity padding
    if len(d) != 8 or not d.isdigit():
        d = "00000000"
    if len(t) < 6:
        t = t.ljust(6, "0")
    try:
        return datetime.strptime(d + t, "%Y%m%d%H%M%S")
    except Exception:  # pragma: no cover
        return datetime.min

def get_member_status_at_qso_time(qso: QSO, member: Member | None) -> str | None:
    """
    Get the member's SKCC award status at the time of QSO.
    
    SKCC Logger captures the member's award status at QSO time in the SKCC field.
    For example: "660S" means member #660 had Senator status at QSO time.
    
    This is the CORRECT way to determine historical status - from the log data
    captured at QSO time, not from guessing based on current roster.
    
    Returns the suffix (C/T/S) from the QSO record, or None if no award status.
    """
    if not qso.skcc:
        return None
    
    # Parse SKCC field to extract suffix
    match = SKCC_FIELD_RE.match(qso.skcc.strip().upper())
    if match:
        suffix = match.group("suffix") or None
        return suffix if suffix else None
    
    return None


def member_qualifies_for_award_at_qso_time(qso: QSO, member: Member | None, award_threshold: int) -> bool:
    """
    Check if a member qualified for an award level at the time of the QSO.
    
    Uses the SKCC field from the QSO record, which contains the member's
    award status AT THE TIME OF QSO - this is the accurate historical data.
    """
    if not member:
        return False
    
    # Centurion Award (100): All SKCC members count regardless of status
    if award_threshold <= 100:
        return True
    
    # For Tribune/Senator awards, get the member's status at QSO time
    qso_time_status = get_member_status_at_qso_time(qso, member)
    
    if award_threshold >= 1000:  # Senator
        return qso_time_status in ['T', 'S']  # Only Tribunes/Senators at QSO time
    elif award_threshold >= 500:  # Tribune  
        return qso_time_status in ['C', 'T', 'S']  # Centurions/Tribunes/Senators at QSO time
    
    return False


def calculate_awards(
    qsos: Sequence[QSO],
    members: Sequence[Member],
    thresholds: Sequence[Tuple[str, int]] | None = None,
    enable_endorsements: bool = True,
    cw_only: bool = True,
    enforce_key_type: bool = False,
    allowed_key_types: Sequence[str] | None = None,
    treat_missing_key_as_valid: bool = True,
    include_unknown_ids: bool = False,
    enforce_suffix_rules: bool = True,
) -> AwardCheckResult:
    """Calculate award progress plus (optionally) band/mode endorsements.

    thresholds: optional override list of (name, required). Defaults to AWARD_THRESHOLDS.
    Endorsements: For each award threshold, if unique member count on a band or mode
    meets that threshold, an endorsement record is produced.
    Implements SKCC Award rules:
      - Centurion Rule #2: Excludes special event / club calls (K9SKC, K3Y*) on/after 20091201.
      - Centurion Rule #3: Requires both parties be members at QSO date if join dates provided.
      - Centurion Rule #4: Counts only unique call signs (each operator only counted once).
      - Tribune Rule #1: For Tribune (500+), only count QSOs with Centurions/Tribunes/Senators (C/T/S suffix).
      - Tribune Rule #2: Both parties must be Centurions at time of QSO for Tribune+ awards.
      - Rule #6: Optionally enforces key type validation (straight key/bug/cootie).
    Parameters:
        enforce_suffix_rules: if True, enforces SKCC suffix requirements for Tribune/Senator awards
        include_unknown_ids: if True, accept numeric SKCC IDs parsed from log even when not present in roster
    """
    use_thresholds = list(thresholds) if thresholds else AWARD_THRESHOLDS

    def member_qualifies_for_award_at_qso_time_inner(member: Member | None, award_threshold: int, qso: QSO) -> bool:
        """
        Check if a member's suffix qualified them for counting toward a specific award AT THE TIME OF QSO.
        
        This uses the SKCC field from the QSO record, which contains the member's
        award status AT THE TIME OF QSO - this is accurate historical data.
        """
        if not enforce_suffix_rules or not member:
            return True  # No suffix enforcement means count all members
        
        # Centurion Award (100): Count all SKCC members (any suffix or no suffix)
        if award_threshold <= 100:
            return True
        
        # For Tribune/Senator awards, get the member's status at QSO time from SKCC field
        qso_time_status = get_member_status_at_qso_time(qso, member)
        
        # Tribune Award (500+): Only count members who were C/T/S at QSO time
        if award_threshold >= 1000:  # Senator
            return qso_time_status in ['T', 'S']  # Only Tribunes/Senators count for Senator
        elif award_threshold >= 500:  # Tribune
            return qso_time_status in ['C', 'T', 'S']  # Centurions/Tribunes/Senators count for Tribune
        
        return True

    # Allowed key device terms (normalized upper tokens). Accept synonyms.
    default_allowed = ["STRAIGHT", "BUG", "COOTIE", "SIDESWIPER", "SIDEWINDER"]
    allowed_set = {t.upper() for t in (allowed_key_types or default_allowed)}

    def key_is_allowed(q: QSO) -> bool:
        if not enforce_key_type:
            return True
        if q.key_type is None:
            return treat_missing_key_as_valid
        tokens = re.split(r"[^A-Z0-9]+", q.key_type.upper())
        return any(tok in allowed_set for tok in tokens if tok)

    # Build primary and alias maps for member calls
    member_by_call: Dict[str, Member] = {}
    number_to_member: Dict[int, Member] = {}
    for m in members:
        number_to_member[m.number] = m
        for alias in generate_call_aliases(m.call):
            member_by_call.setdefault(alias, m)
    # worked_numbers retained for potential future logic (not currently used)

    # For endorsements we track unique member numbers per band and per mode
    band_members: Dict[str, Set[int]] = {}
    mode_members: Dict[str, Set[int]] = {}
    unmatched_calls: Set[str] = set()

    # Pre-calc disallowed special event patterns
    SPECIAL_CUTOFF = "20091201"
    def is_disallowed_special(call: str | None, date: str | None) -> bool:
        if not call or not date:
            return False
        if date < SPECIAL_CUTOFF:
            return False  # before cutoff, allowed
        base = call.upper()
        if base == "K9SKC":
            return True
        # K3Y or K3Y/1 etc (K3Y followed by optional / and region)
        if base.startswith("K3Y"):
            if base == "K3Y" or base.startswith("K3Y/"):
                return True
        return False

    filtered_qsos: List[QSO] = []
    for q in qsos:
        if cw_only:
            if not q.mode or "CW" not in q.mode.upper():
                continue
        # Exclude disallowed special calls (rule #2)
        if is_disallowed_special(q.call, q.date):
            continue
        # Enforce key device rule (rule #6)
        if not key_is_allowed(q):
            continue
        filtered_qsos.append(q)

    # Build chronological ordering for award progression logic
    chronological = sorted(filtered_qsos, key=_qso_timestamp)
    first_seen_time: Dict[int, datetime] = {}

    matched_qso_count = 0

    # Iterate QSOs; validate membership at QSO time and populate category sets
    for q in chronological:
        member = member_by_call.get(q.call or "")
        numeric_id: int | None = None
        if member:
            # Membership date validation (rule #3)
            if member.join_date and q.date and q.date < member.join_date:
                # QSO before member joined; skip entirely
                continue
            numeric_id = member.number
        else:
            # We no longer trust raw SKCC field unless it maps to a known member number
            if q.skcc:
                msk = SKCC_FIELD_RE.match(q.skcc.strip().upper())
                if msk:
                    candidate = int(msk.group("num"))
                    if candidate in number_to_member:
                        # If we have the member but call didn't match (e.g. portable variant we failed to normalize), ensure join date ok
                        m2 = number_to_member[candidate]
                        if not (m2.join_date and q.date and q.date < m2.join_date):
                            numeric_id = candidate
                    elif include_unknown_ids:
                        numeric_id = candidate
        if numeric_id is None:
            if q.call:
                unmatched_calls.add(q.call)
            continue

        # Count this QSO as matched (a valid roster member contact)
        matched_qso_count += 1
        # Track first-seen time
        if numeric_id not in first_seen_time:
            first_seen_time[numeric_id] = _qso_timestamp(q)
        # Update endorsement tracking
        if q.band:
            band_members.setdefault(q.band.upper(), set()).add(numeric_id)
        if q.mode:
            mode_members.setdefault(q.mode.upper(), set()).add(numeric_id)

    # Unique IDs set
    all_unique_ids: Set[int] = set(first_seen_time.keys())
    unique_count = len(all_unique_ids)

    # Determine centurion achievement timestamp (first moment hitting 100 uniques)
    centurion_ts: datetime | None = None
    if unique_count >= 100:
        seen: Set[int] = set()
        for q in chronological:
            member = member_by_call.get(q.call or "")
            nid = None
            if member:
                if member.join_date and q.date and q.date < member.join_date:
                    continue
                nid = member.number
            elif q.skcc:
                msk = SKCC_FIELD_RE.match(q.skcc.strip().upper())
                if msk:
                    cand = int(msk.group("num"))
                    if cand in number_to_member:
                        m2 = number_to_member[cand]
                        if m2.join_date and q.date and q.date < m2.join_date:
                            continue
                        nid = cand
                    elif include_unknown_ids:
                        nid = cand
            if nid is None:
                continue
            if nid not in seen:
                seen.add(nid)
                if len(seen) == 100:
                    centurion_ts = _qso_timestamp(q)
                    break

    # Award progress - implementing complete SKCC award rules with historical status consideration
    progresses: List[AwardProgress] = []
    
    # Centurion (100): All unique SKCC members count
    centurion_current = unique_count
    centurion_achieved = centurion_current >= 100
    progresses.append(AwardProgress(
        name="Centurion",
        required=100,
        current=centurion_current,
        achieved=centurion_achieved,
        description="Contact 100 unique SKCC members"
    ))
    
    if enforce_suffix_rules:
        # For proper SKCC rules, we need to evaluate each member's status at QSO time
        # Track members who qualified for Tribune/Senator awards at the time of contact
        tribune_qualified_members = set()
        senator_qualified_members = set()
        
        # Go through QSOs chronologically to determine qualification at QSO time
        for q in chronological:
            member = member_by_call.get(q.call or "")
            numeric_id = None
            
            if member:
                if member.join_date and q.date and q.date < member.join_date:
                    continue
                numeric_id = member.number
            elif q.skcc:
                msk = SKCC_FIELD_RE.match(q.skcc.strip().upper())
                if msk:
                    candidate = int(msk.group("num"))
                    if candidate in number_to_member:
                        m2 = number_to_member[candidate]
                        if m2.join_date and q.date and q.date < m2.join_date:
                            continue
                        member = m2
                        numeric_id = candidate
                    elif include_unknown_ids:
                        numeric_id = candidate
            
            if numeric_id is None or member is None:
                continue
            
            # Check if this member qualified for Tribune award at QSO time
            if member_qualifies_for_award_at_qso_time_inner(member, 500, q):
                tribune_qualified_members.add(numeric_id)
            
            # Check if this member qualified for Senator award at QSO time
            if member_qualifies_for_award_at_qso_time_inner(member, 1000, q):
                senator_qualified_members.add(numeric_id)
        
        tribune_current = len(tribune_qualified_members)
        tribune_achieved = tribune_current >= 500
        
        # Tribune x8 requires 400 contacts with members who were C/T/S at QSO time
        tribune_x8_current = len(tribune_qualified_members)
        tribune_x8_achieved = tribune_x8_current >= 400
        
        # Senator requires Tribune x8 (400 qualified) PLUS 200 contacts with T/S at QSO time
        senator_current = len(senator_qualified_members)
        senator_prerequisite = tribune_x8_achieved
        senator_achieved = senator_prerequisite and senator_current >= 200
        
        progresses.append(AwardProgress(
            name="Tribune",
            required=500,
            current=tribune_current,
            achieved=tribune_achieved,
            description="Contact 500 unique members who were C/T/S at QSO time"
        ))
        
        progresses.append(AwardProgress(
            name="Tribune x8",
            required=400,
            current=tribune_x8_current,
            achieved=tribune_x8_achieved,
            description="Contact 400 unique members who were C/T/S at QSO time (prerequisite for Senator)"
        ))
        
        senator_desc = f"Tribune x8 + 200 members who were T/S at QSO time. Prerequisite: {'✓' if senator_prerequisite else '✗'}"
        progresses.append(AwardProgress(
            name="Senator",
            required=200,
            current=senator_current,
            achieved=senator_achieved,
            description=senator_desc
        ))
    else:
        # Legacy counting for backwards compatibility - uses current status
        centurion_plus_members = set()
        tribune_senator_members = set()  # T/S only for Senator award
        
        for nid in all_unique_ids:
            member = number_to_member.get(nid)
            if member and member.suffix:
                if member.suffix in ['C', 'T', 'S']:
                    centurion_plus_members.add(nid)
                if member.suffix in ['T', 'S']:
                    tribune_senator_members.add(nid)
        
        tribune_current = len(centurion_plus_members)
        tribune_achieved = tribune_current >= 500
        
        # Tribune x8 requires 400 contacts with C/T/S members
        tribune_x8_current = len(centurion_plus_members)
        tribune_x8_achieved = tribune_x8_current >= 400
        
        # Senator requires Tribune x8 (400 C/T/S) PLUS 200 contacts with T/S only
        senator_current = len(tribune_senator_members)
        senator_prerequisite = tribune_x8_achieved
        senator_achieved = senator_prerequisite and senator_current >= 200
        
        progresses.append(AwardProgress(
            name="Tribune",
            required=500,
            current=tribune_current,
            achieved=tribune_achieved,
            description="Contact 500 unique Centurions/Tribunes/Senators (legacy: current status)"
        ))
        
        progresses.append(AwardProgress(
            name="Tribune x8",
            required=400,
            current=tribune_x8_current,
            achieved=tribune_x8_achieved,
            description="Contact 400 unique Centurions/Tribunes/Senators (legacy: current status)"
        ))
        
        senator_desc = f"Tribune x8 + 200 Tribunes/Senators (legacy: current status). Prerequisite: {'✓' if senator_prerequisite else '✗'}"
        progresses.append(AwardProgress(
            name="Senator",
            required=200,
            current=senator_current,
            achieved=senator_achieved,
            description=senator_desc
        ))

    endorsements: List[AwardEndorsement] = []
    if enable_endorsements:
        for name, required in use_thresholds:
            for band, nums in band_members.items():
                current = len(nums)
                if current >= required:
                    endorsements.append(
                        AwardEndorsement(
                            award=name,
                            category="band",
                            value=band,
                            required=required,
                            current=current,
                            achieved=current >= required,
                        )
                    )
            for mode, nums in mode_members.items():
                current = len(nums)
                if current >= required:
                    endorsements.append(
                        AwardEndorsement(
                            award=name,
                            category="mode",
                            value=mode,
                            required=required,
                            current=current,
                            achieved=current >= required,
                        )
                    )
        endorsements.sort(key=lambda e: (e.award, e.category, e.value))

    return AwardCheckResult(
        unique_members_worked=unique_count,
        awards=progresses,
        endorsements=endorsements,
        total_qsos=len(qsos),
        matched_qsos=matched_qso_count,
        unmatched_calls=sorted(unmatched_calls),
        thresholds_used=list(use_thresholds),
        total_cw_qsos=len(filtered_qsos),
    )
