# ruff: noqa: PLW0603, BLE001
# pylint: disable=global-statement,broad-exception-caught
"""NOAA SWPC space weather helpers.

Lightweight fetchers for up-to-the-minute radio-relevant indicators:
- Kp index (geomagnetic activity)
- IMF Bz/Bt (solar wind magnetic field)
- GOES X-ray flux and class

Design goals:
- Resilient to endpoint hiccups: try multiple well-known SWPC JSON feeds
- Short-lived cache to avoid spamming endpoints and keep the UI snappy
- Zero heavy deps (httpx only) and safe timeouts
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

# ------------------------------ Config ---------------------------------

# 60 seconds cache window; GUI refreshes every minute by default
_CACHE_TTL = timedelta(seconds=60)

# Conservative timeouts; keep UI responsive even if network stalls
_HTTP_TIMEOUT = httpx.Timeout(connect=3.0, read=3.5, write=3.0, pool=2.0)


@dataclass
class SpaceWeatherSnapshot:
    kp: float | None
    kp_time: datetime | None
    bz: float | None  # nT (GSM)
    bt: float | None  # nT
    sw_time: datetime | None
    xray_flux: float | None  # W/m^2 (0.1–0.8 nm preferred)
    xray_time: datetime | None
    sfi: float | None  # 10.7 cm solar radio flux
    sfi_time: datetime | None
    ssn: float | None  # Sunspot Number (International, if available)
    ssn_time: datetime | None
    a_index: float | None  # Estimated planetary A-index (fallback Boulder)
    a_time: datetime | None


_cache_value: SpaceWeatherSnapshot | None = None
_cache_time: datetime | None = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def summarize_for_ui() -> tuple[str, str, str, str, str, str]:
    """Return concise strings for the legacy full GUI labels.

    Kept for backward compatibility (Kp, Bz/Bt, X-ray, SFI, A, Updated)
    even though the streamlined panel now only uses a subset.
    """
    snap = get_space_weather()

    # Kp text
    kp_text = "Kp —"
    if snap.kp is not None:
        kp_text = f"Kp {snap.kp:.1f}"

    # Magnetic field text (IMF)
    mag_text = "Bz/Bt —"
    if snap.bz is not None or snap.bt is not None:
        bz = f"{snap.bz:.1f} nT" if snap.bz is not None else "—"
        bt = f"{snap.bt:.1f} nT" if snap.bt is not None else "—"
        mag_text = f"Bz {bz}  Bt {bt}"

    # X-ray text with GOES class
    xray_text = "X-ray —"
    if snap.xray_flux is not None:
        letter, mag = _goes_xray_class(snap.xray_flux)
        xray_text = f"X-ray {letter}{mag:.1f} ({snap.xray_flux:.1e} W/m²)"

    # SFI text
    sfi_text = "SFI —"
    if snap.sfi is not None:
        sfi_text = f"SFI {snap.sfi:.0f}"

    # A-index text
    a_text = "A —"
    if snap.a_index is not None:
        a_text = f"A {snap.a_index:.0f}"

    # Updated label
    newest = max(
        [
            t
            for t in [
                snap.kp_time,
                snap.sw_time,
                snap.xray_time,
                snap.sfi_time,
                snap.a_time,
            ]
            if t is not None
        ],
        default=None,
    )
    if newest is None:
        updated = "Updated —"
    else:
        # Show as UTC HH:MM
        updated = f"Updated {newest.astimezone(timezone.utc).strftime('%H:%M')}Z"

    return kp_text, mag_text, xray_text, sfi_text, a_text, updated


def summarize_for_ui_minimal() -> tuple[str, str, str, str, str]:
    """Return concise strings for the simplified GUI panel.

    Returns:
        (kp_text, sfi_text, ssn_text, a_text, updated_text)
    """
    snap = get_space_weather()

    kp_text = "Kp —" if snap.kp is None else f"Kp {snap.kp:.1f}"
    sfi_text = "SFI —" if snap.sfi is None else f"SFI {snap.sfi:.0f}"
    ssn_text = "SSN —" if snap.ssn is None else f"SSN {snap.ssn:.0f}"
    a_text = "A —" if snap.a_index is None else f"A {snap.a_index:.0f}"

    newest = max(
        [
            t
            for t in [
                snap.kp_time,
                snap.sfi_time,
                snap.ssn_time,
                snap.a_time,
            ]
            if t is not None
        ],
        default=None,
    )
    updated = (
        "Updated —"
        if newest is None
        else f"Updated {newest.astimezone(timezone.utc).strftime('%H:%M')}Z"
    )
    return kp_text, sfi_text, ssn_text, a_text, updated


def get_space_weather(force: bool = False) -> SpaceWeatherSnapshot:
    """Fetch space weather now-cast with a short cache.

    If `force` is False and cache is fresh, returns cached data.
    """
    global _cache_value, _cache_time  # noqa: PLW0603  # pylint: disable=global-statement

    if (
        not force
        and _cache_value is not None
        and _cache_time is not None
        and _now_utc() - _cache_time < _CACHE_TTL
    ):
        return _cache_value

    kp_val, kp_time = _fetch_kp()
    bz, bt, sw_time = _fetch_imf_bz_bt()
    xflux, x_time = _fetch_goes_xray()
    sfi_val, sfi_time, ssn_val, ssn_time, a_val, a_time = _fetch_sfi_a_ssn()

    snap = SpaceWeatherSnapshot(
        kp=kp_val,
        kp_time=kp_time,
        bz=bz,
        bt=bt,
        sw_time=sw_time,
        xray_flux=xflux,
        xray_time=x_time,
        sfi=sfi_val,
        sfi_time=sfi_time,
        ssn=ssn_val,
        ssn_time=ssn_time,
        a_index=a_val,
        a_time=a_time,
    )

    _cache_value = snap
    _cache_time = _now_utc()
    return snap


# ------------------------------ Fetchers ---------------------------------


def _safe_get_json(client: httpx.Client, url: str) -> Any | None:
    try:
        r = client.get(url)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _parse_time(s: str) -> datetime | None:
    # Try common time formats used by SWPC feeds
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _fetch_kp() -> tuple[float | None, datetime | None]:
    """Fetch latest Kp value.

    Tries a set of known SWPC endpoints; returns (kp, time_utc)
    """
    urls: list[str] = [
        # Minute cadence (if available)
        "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
        # 3-hour cadence (widely available)
        "https://services.swpc.noaa.gov/json/planetary_k_index_3h.json",
    ]

    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        for url in urls:
            data = _safe_get_json(client, url)
            if not isinstance(data, list) or not data:
                continue
            # Find the latest item by time-like fields
            latest = None
            latest_t: datetime | None = None
            for item in data:
                if not isinstance(item, dict):
                    continue
                # Candidate time keys seen across feeds
                t = (
                    item.get("time_tag")
                    or item.get("time")
                    or item.get("end_time")
                    or item.get("end")
                )
                dt = _parse_time(t) if isinstance(t, str) else None
                if (
                    latest is None
                    or (dt and latest_t and dt > latest_t)
                    or (latest is None and dt is not None)
                ):
                    latest = item
                    latest_t = dt
            if latest is None:
                continue
            # Candidate value keys across feeds
            for key in ("kp", "kp_index", "estimated_kp", "kpm"):
                val = latest.get(key)
                try:
                    if val is None:
                        continue
                    kp_val = float(val)
                    return kp_val, latest_t
                except Exception:
                    continue

    return None, None


def _fetch_imf_bz_bt() -> tuple[float | None, float | None, datetime | None]:
    """Fetch latest IMF Bz (GSM) and Bt from DSCOVR feeds.

    Returns (bz, bt, time_utc) in nT.
    """
    urls: list[str] = [
        # Newer consolidated DSCOVR feed
        "https://services.swpc.noaa.gov/json/dscovr_solar_wind_1m.json",
        # Fallbacks (naming variants)
        "https://services.swpc.noaa.gov/json/dscovr_solar_wind.json",
        # Legacy ACE real-time magnetometer (units also in nT)
        "https://services.swpc.noaa.gov/json/ace/rtmag_1m.json",
    ]

    def pick_latest(
        items: list[dict[str, Any]],
    ) -> tuple[float | None, float | None, datetime | None]:
        best: tuple[float | None, float | None, datetime | None] = (None, None, None)
        best_time: datetime | None = None
        for it in items:
            if not isinstance(it, dict):
                continue
            t = it.get("time_tag") or it.get("time") or it.get("timestamp")
            dt = _parse_time(t) if isinstance(t, str) else None
            if dt is None:
                continue
            try:
                # DSCOVR: bz_gsm, bt
                bz = it.get("bz_gsm")
                bt = it.get("bt")
                # ACE: Bz (nT), Bt (nT)
                if bz is None:
                    bz = it.get("bz") or it.get("bz_gsm")
                if bt is None:
                    bt = it.get("bt") or it.get("total_field")
                bz_f = float(bz) if bz is not None else None
                bt_f = float(bt) if bt is not None else None
            except Exception:
                continue
            if best_time is None or dt > best_time:
                best = (bz_f, bt_f, dt)
                best_time = dt
        return best

    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        for url in urls:
            data = _safe_get_json(client, url)
            if not isinstance(data, list) or not data:
                continue
            bz, bt, dt = pick_latest(data)
            if dt is not None:
                return bz, bt, dt

    return None, None, None


def _fetch_goes_xray() -> tuple[float | None, datetime | None]:
    """Fetch latest GOES X-ray flux (0.1–0.8 nm preferred). Returns (flux, time_utc)."""
    urls: list[str] = [
        # Primary consolidated 1-day feed (primary satellite)
        "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json",
        # Older naming variants
        "https://services.swpc.noaa.gov/json/goes_xray_flux_1m.json",
        "https://services.swpc.noaa.gov/json/goes/integrated-xray-flux-1m.json",
    ]

    def pick_latest(items: list[dict[str, Any]]) -> tuple[float | None, datetime | None]:
        # We prefer the long band 0.1–0.8 nm if both are present
        best_flux: float | None = None
        best_time: datetime | None = None
        for it in items:
            if not isinstance(it, dict):
                continue
            # Energy/band keys vary; accept any and prefer long band
            energy = (it.get("energy") or it.get("wavelength") or "").lower()
            t = it.get("time_tag") or it.get("time") or it.get("timestamp")
            dt = _parse_time(t) if isinstance(t, str) else None
            if dt is None:
                continue
            # Candidate flux keys
            flux_val = it.get("flux") or it.get("xray_flux") or it.get("value")
            try:
                flux = float(flux_val) if flux_val is not None else None
            except Exception:
                continue
            if flux is None:
                continue
            # Prefer long band if mentioned, otherwise accept last datum chronologically
            prefers_long = any(x in energy for x in ("0.1-0.8", "0.1 – 0.8", "long"))
            if best_time is None or dt > best_time or prefers_long:
                best_flux, best_time = flux, dt
        return best_flux, best_time

    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        for url in urls:
            data = _safe_get_json(client, url)
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                data = data["data"]
            if not isinstance(data, list) or not data:
                continue
            flux, dt = pick_latest(data)
            if dt is not None and flux is not None:
                return flux, dt

    return None, None


# noqa: PLR0915 - the parsing function is intentionally explicit for robustness
def _fetch_sfi_a_ssn() -> tuple[
    float | None,
    datetime | None,
    float | None,
    datetime | None,
    float | None,
    datetime | None,
]:
    """Fetch latest SFI (F10.7 cm flux), Sunspot Number (SSN) and A-index.

    Primary source: NOAA SWPC WWV geophysical alert text, which includes
    lines like: "Solar flux 140 and estimated planetary A-index 8." and may
    also contain a "Sunspot number 132" line.

    Returns (sfi, sfi_time, ssn, ssn_time, a_index, a_time).
    """
    # WWV text is updated several times per day and is reliable for hams
    url = "https://services.swpc.noaa.gov/text/wwv.txt"

    def parse_issued_timestamp(lines: list[str]) -> datetime | None:
        # Typical line: "Issued: 2024 Sep 04 2205 UTC"
        import re

        month_map = {
            "Jan": 1,
            "Feb": 2,
            "Mar": 3,
            "Apr": 4,
            "May": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12,
        }
        pat = re.compile(r"Issued:\s*(\d{4})\s+([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})\s+UTC")
        for line in lines:
            m = pat.search(line)
            if m:
                year = int(m.group(1))
                mon = month_map.get(m.group(2), 1)
                day = int(m.group(3))
                hhmm = m.group(4)
                hour = int(hhmm[:2])
                minute = int(hhmm[2:])
                return datetime(year, mon, day, hour, minute, tzinfo=timezone.utc)
        return None

    def parse_sfi_a_ssn(lines: list[str]) -> tuple[float | None, float | None, float | None]:
        import re

        sfi_val: float | None = None
        a_val: float | None = None
        ssn_val: float | None = None
        # Search the conventional summary line
        # Examples:
        # Example line:
        # "Solar-terrestrial indices for 04 Sep 2024 follow.  Solar flux 140 and estimated"
        # "planetary A-index 8.  The estimated planetary K-index..."
        # Older variants may say "Boulder A-index" instead of planetary.
        sfi_pat = re.compile(r"Solar\s+flux\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
        a_planet_pat = re.compile(r"planetary\s+A-index\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
        a_boulder_pat = re.compile(r"Boulder\s+A-index\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
        ssn_pat = re.compile(r"Sunspot\s+number\s+(\d+(?:\.\d+)?)", re.IGNORECASE)

        for line in lines:
            if sfi_val is None:
                ms = sfi_pat.search(line)
                if ms:
                    with contextlib.suppress(Exception):
                        sfi_val = float(ms.group(1))
            if a_val is None:
                ma = a_planet_pat.search(line)
                if ma:
                    with contextlib.suppress(Exception):
                        a_val = float(ma.group(1))
            if a_val is None:
                mb = a_boulder_pat.search(line)
                if mb:
                    with contextlib.suppress(Exception):
                        a_val = float(mb.group(1))
            if ssn_val is None:
                msun = ssn_pat.search(line)
                if msun:
                    with contextlib.suppress(Exception):
                        ssn_val = float(msun.group(1))
            if sfi_val is not None and a_val is not None and ssn_val is not None:
                break
        return sfi_val, ssn_val, a_val

    # First try WWV bulletin
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            r = client.get(url)
            r.raise_for_status()
            text = r.text
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            sfi_val, ssn_val, a_val = parse_sfi_a_ssn(lines)
            ts = parse_issued_timestamp(lines)
            if (sfi_val is not None or a_val is not None or ssn_val is not None) and ts is not None:
                return sfi_val, ts, ssn_val, ts, a_val, ts
    except Exception:
        pass

    # Fallback: Daily solar data text (once-per-day products; timestamp approximated to 20:00Z)
    # https://services.swpc.noaa.gov/text/daily-solar-data.txt
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            r = client.get("https://services.swpc.noaa.gov/text/daily-solar-data.txt")
            r.raise_for_status()
            text = r.text
    except Exception:
        return None, None, None, None, None, None

    # Parse basic SFI and A from daily solar data
    # Look for patterns like:
    #  - "10.7 cm flux:  144" or "SF: 144"
    #  - "Ap: 8" or "Planetary A index: 8"
    try:
        import re

        sfi_val: float | None = None
        a_val: float | None = None
        ssn_val: float | None = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if sfi_val is None:
                m1 = re.search(
                    r"(10\.7\s*cm\s*flux|solar\s*flux|sfi)\s*[:=]\s*(\d+(?:\.\d+)?)",
                    line,
                    re.IGNORECASE,
                )
                if m1:
                    with contextlib.suppress(Exception):
                        sfi_val = float(m1.group(2))
            if ssn_val is None:
                mssn = re.search(
                    r"(sunspot\s+number|sunspot\s*#|ssn)\s*[:=]\s*(\d+(?:\.\d+)?)",
                    line,
                    re.IGNORECASE,
                )
                if mssn:
                    with contextlib.suppress(Exception):
                        ssn_val = float(mssn.group(2))
            if a_val is None:
                m2 = re.search(
                    r"(\bAp\b|planetary\s*A\s*index|A-index)\s*[:=]\s*(\d+(?:\.\d+)?)",
                    line,
                    re.IGNORECASE,
                )
                if m2:
                    with contextlib.suppress(Exception):
                        a_val = float(m2.group(2))
            if sfi_val is not None and a_val is not None and ssn_val is not None:
                break

        # Daily data is reported for the UTC date; use today's 20:00Z as an approximate timestamp
        ts = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
        return sfi_val, ts, ssn_val, ts, a_val, ts
    except Exception:
        return None, None, None, None, None, None


# ------------------------------ Helpers ---------------------------------


GOES_A_THRESH = 1e-7
GOES_B_THRESH = 1e-6
GOES_C_THRESH = 1e-5
GOES_M_THRESH = 1e-4


def _goes_xray_class(flux_w_m2: float) -> tuple[str, float]:
    """Convert flux in W/m^2 to GOES X-ray class (A/B/C/M/X and magnitude).

    Example: 5e-6 -> ("C", 5.0)
    """
    # GOES scale thresholds in W/m^2
    # A: <1e-7, B: 1e-7–1e-6, C: 1e-6–1e-5, M: 1e-5–1e-4, X: >=1e-4
    if flux_w_m2 < GOES_A_THRESH:
        return "A", flux_w_m2 / GOES_A_THRESH
    if flux_w_m2 < GOES_B_THRESH:
        return "B", flux_w_m2 / GOES_B_THRESH
    if flux_w_m2 < GOES_C_THRESH:
        return "C", flux_w_m2 / GOES_C_THRESH
    if flux_w_m2 < GOES_M_THRESH:
        return "M", flux_w_m2 / GOES_M_THRESH
    return "X", flux_w_m2 / GOES_M_THRESH


__all__ = [
    "summarize_for_ui",
    "summarize_for_ui_minimal",
    "get_space_weather",
    "SpaceWeatherSnapshot",
]
