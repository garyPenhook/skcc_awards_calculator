import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the repo root to Python path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.qso import QSO
from models.key_type import normalize
from adif_io.adif_writer import append_record

def main(argv=None):
    ap = argparse.ArgumentParser("skcc qso — append a QSO to ADIF")
    ap.add_argument("--adif", required=True, help="ADIF file to create/append")
    ap.add_argument("--call", required=True)
    ap.add_argument("--when-utc", help="YYYYMMDDHHMMSS (default: now UTC)")
    ap.add_argument("--freq", type=float, help="MHz (optional)")
    ap.add_argument("--band", help="e.g. 40M if no freq")
    ap.add_argument("--rst-s", default="599")
    ap.add_argument("--rst-r", default="599")
    ap.add_argument("--station", dest="station_callsign")
    ap.add_argument("--op", dest="operator")
    ap.add_argument("--pwr", type=float, dest="tx_pwr_w")
    ap.add_argument("--skcc", dest="their_skcc", help="Their SKCC number (e.g. 22224T)")
    ap.add_argument("--my-skcc", dest="my_skcc")
    ap.add_argument("--key", required=True, help="straight|bug|sideswiper")

    args = ap.parse_args(argv)
    when = (datetime.strptime(args.when_utc, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            if args.when_utc else datetime.now(timezone.utc))

    q = QSO(
        call=args.call, when=when, freq_mhz=args.freq, band=args.band,
        rst_s=args.rst_s, rst_r=args.rst_r, station_callsign=args.station_callsign,
        operator=args.operator, tx_pwr_w=args.tx_pwr_w, their_skcc=args.their_skcc,
        my_skcc=args.my_skcc, my_key=normalize(args.key),
    )
    append_record(args.adif, q.to_adif_fields())

if __name__ == "__main__":
    main()
