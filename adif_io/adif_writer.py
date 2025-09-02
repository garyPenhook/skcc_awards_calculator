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
    """Ensure ADIF file has proper header, with error handling."""
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        header = []
        header.append(_hdr_line("ADIF_VER", ADIF_VERSION))
        header.append(_hdr_line("PROGRAMID", PROGRAMID))
        header.append(_hdr_line("PROGRAMVERSION", PROGRAMVERSION))
        header.append(_hdr_line("CREATED_TIMESTAMP", _now_utc_str()))
        header.append("<EOH>\n")

        # Use temporary file for atomic write
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="ascii", errors="strict") as f:
                f.writelines(header)
            os.replace(tmp, path)
        except Exception:
            # Clean up temp file if write failed
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    except PermissionError:
        raise PermissionError(f"Permission denied writing to ADIF file: {path}")
    except OSError as e:
        raise OSError(f"Error creating ADIF file {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error creating ADIF header: {e}")


def _encode_field(tag: str, value: str) -> str:
    return f"<{tag}:{len(value)}>{value}"


def append_record(path: str, fields: Iterable[tuple[str, str]]) -> None:
    """Append a QSO record to ADIF file, with error handling."""
    try:
        ensure_header(path)

        # Build record
        rec = []
        for tag, val in fields:
            if not isinstance(tag, str) or not isinstance(val, str):
                raise ValueError(f"ADIF field must be strings: {tag}={val}")
            rec.append(_encode_field(tag, val))
        rec.append("<EOR>\n")

        # Atomic append operation
        record_data = "".join(rec).encode("ascii", errors="strict")

        with open(path, "ab") as f:
            f.write(record_data)

    except UnicodeEncodeError as e:
        raise ValueError(f"Invalid characters in ADIF record (ASCII required): {e}")
    except PermissionError:
        raise PermissionError(f"Permission denied writing to ADIF file: {path}")
    except OSError as e:
        if "No space left on device" in str(e):
            raise OSError(f"Disk full - cannot write to ADIF file: {path}")
        else:
            raise OSError(f"Error writing to ADIF file {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error writing ADIF record: {e}")
