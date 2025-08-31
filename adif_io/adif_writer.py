import os
from datetime import datetime, timezone
from typing import Iterable

ADIF_VERSION = "3.1.5"
PROGRAMID = "SKCC_Awards_Calculator"
PROGRAMVERSION = "1.0.0"

def _hdr_line(tag: str, val: str) -> str:
    return f"<{tag}:{len(val)}>{val}\n"

def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d %H%M%S")

def ensure_header(path: str) -> None:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    header = []
    header.append(_hdr_line("ADIF_VER", ADIF_VERSION))
    header.append(_hdr_line("PROGRAMID", PROGRAMID))
    header.append(_hdr_line("PROGRAMVERSION", PROGRAMVERSION))
    header.append(_hdr_line("CREATED_TIMESTAMP", _now_utc_str()))
    header.append("<EOH>\n")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii", errors="strict") as f:
        f.writelines(header)
    os.replace(tmp, path)

def _encode_field(tag: str, value: str) -> str:
    return f"<{tag}:{len(value)}>{value}"

def append_record(path: str, fields: Iterable[tuple[str, str]]) -> None:
    ensure_header(path)
    with open(path, "ab") as f:
        rec = []
        for tag, val in fields:
            rec.append(_encode_field(tag, val))
        rec.append("<EOR>\n")
        f.write("".join(rec).encode("ascii", errors="strict"))
