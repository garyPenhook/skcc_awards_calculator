from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from .key_type import KeyType, DISPLAY_LABELS
from utils.bandplan import freq_to_band


@dataclass
class QSO:
    call: str
    when: datetime  # Start time - naive or aware; stored as UTC
    mode: str = "CW"
    freq_mhz: Optional[float] = None
    band: Optional[str] = None
    rst_s: Optional[str] = None
    rst_r: Optional[str] = None
    station_callsign: Optional[str] = None
    operator: Optional[str] = None
    tx_pwr_w: Optional[float] = None
    their_skcc: Optional[str] = None
    my_skcc: Optional[str] = None
    my_key: Optional[KeyType] = None  # REQUIRED for Triple Key
    # QTH information
    country: Optional[str] = None
    state: Optional[str] = None
    # End time for ragchew award tracking
    time_off: Optional[datetime] = None

    @staticmethod
    def _utc(date: datetime) -> datetime:
        if date.tzinfo is None:
            return date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)

    def to_adif_fields(self) -> list[tuple[str, str]]:
        if not self.my_key:
            raise ValueError("Key type is required for Triple Key logging.")
        utc = QSO._utc(self.when)
        qso_date = utc.strftime("%Y%m%d")
        time_on = utc.strftime("%H%M%S")
        band = self.band or (freq_to_band(self.freq_mhz) if self.freq_mhz is not None else None)

        fields: list[tuple[str, str]] = []

        def put(tag: str, val: Optional[str]):
            if val not in (None, ""):
                fields.append((tag, str(val)))

        put("CALL", self.call.upper())
        put("QSO_DATE", qso_date)
        put("TIME_ON", time_on)

        # Add TIME_OFF if available (for ragchew award tracking)
        if self.time_off:
            utc_off = QSO._utc(self.time_off)
            time_off = utc_off.strftime("%H%M%S")
            put("TIME_OFF", time_off)

        put("MODE", self.mode)
        if self.freq_mhz is not None:
            put("FREQ", f"{self.freq_mhz:.4f}")  # 4 dp is common
        if band:
            put("BAND", band)
        put("RST_SENT", self.rst_s)
        put("RST_RCVD", self.rst_r)
        put("STATION_CALLSIGN", self.station_callsign)
        put("OPERATOR", self.operator)
        if self.tx_pwr_w is not None:
            put("TX_PWR", f"{self.tx_pwr_w:g}")

        # SKCC via standard SIG fields
        if self.their_skcc:
            put("SIG", "SKCC")
            put("SIG_INFO", self.their_skcc)
            # Also write commonly-used custom SKCC tag for better compatibility
            put("SKCC", self.their_skcc)
        if self.my_skcc:
            put("MY_SIG", "SKCC")
            put("MY_SIG_INFO", self.my_skcc)

        # ADIF 3.1.5 standard: your key type
        put("MY_MORSE_KEY_TYPE", DISPLAY_LABELS[self.my_key])

        # QTH information
        put("COUNTRY", self.country)
        put("STATE", self.state)

        # App-scoped mirrors for robust parsing in downstream tools
        # Canonical key tokens expected by backend: STRAIGHT, BUG, SIDESWIPER
        key_canonical = {
            "straight": "STRAIGHT",
            "bug": "BUG",
            "sideswiper": "SIDESWIPER",
        }.get(self.my_key.value.lower(), self.my_key.value.upper())
        put("APP_SKCCLOGGER_KEYTYPE", key_canonical)
        put("APP_SKCCAC_KEY", self.my_key.value)

        # Auto-generate a helpful COMMENT with SKCC and operating details
        comment_parts: list[str] = []
        if self.their_skcc:
            # Parser looks for the pattern "SKCC: <number>" in comments
            comment_parts.append(f"SKCC: {self.their_skcc}")
        # Include key type with friendly label and canonical token for search
        if self.my_key:
            label = DISPLAY_LABELS[self.my_key]
            if key_canonical and key_canonical not in label.upper():
                comment_parts.append(f"Key: {label} ({key_canonical})")
            else:
                comment_parts.append(f"Key: {label}")
        if band:
            comment_parts.append(f"Band: {band}")
        elif self.freq_mhz is not None:
            comment_parts.append(f"Freq: {self.freq_mhz:.4f} MHz")
        if self.rst_s or self.rst_r:
            sent = self.rst_s or ""
            rcvd = self.rst_r or ""
            if sent or rcvd:
                comment_parts.append(f"RST {sent}/{rcvd}")
        if self.tx_pwr_w is not None:
            pwr_text = f"PWR {self.tx_pwr_w:g}W"
            if self.tx_pwr_w <= 5:
                pwr_text += " QRP"  # Helps QRP detection
            comment_parts.append(pwr_text)
        if self.state:
            comment_parts.append(f"State: {self.state}")
        if self.country:
            comment_parts.append(f"DXCC: {self.country}")
        # Include duration if end time provided
        if self.time_off:
            dur_sec = int((QSO._utc(self.time_off) - utc).total_seconds())
            if dur_sec >= 0:
                mins, secs = divmod(dur_sec, 60)
                if mins or secs:
                    comment_parts.append(f"Dur: {mins}m{secs:02d}s")
        if comment_parts:
            # Ensure ASCII-safe content (writer will enforce ASCII)
            comment = " | ".join(comment_parts)
            put("COMMENT", comment)
        return fields
