from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from .key_type import KeyType, DISPLAY_LABELS
from utils.bandplan import freq_to_band

@dataclass
class QSO:
    call: str
    when: datetime               # naive or aware; stored as UTC
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
        if self.my_skcc:
            put("MY_SIG", "SKCC")
            put("MY_SIG_INFO", self.my_skcc)

        # ADIF 3.1.5 standard: your key type
        put("MY_MORSE_KEY_TYPE", DISPLAY_LABELS[self.my_key])

        # QTH information
        put("COUNTRY", self.country)
        put("STATE", self.state)

        # App-scoped mirror for robust parsing
        put("APP_SKCCAC_KEY", self.my_key.value)
        return fields
