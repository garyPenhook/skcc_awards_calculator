#!/usr/bin/env python3
"""SKCC Cluster Spot Manager - Connects to CW-Club RBN Gateway for SKCC-filtered spots."""

import re
import socket
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# Frequency ranges for amateur HF bands (MHz)
BAND_RANGES: List[tuple[str, float, float]] = [
    ("160M", 1.8, 2.0),
    ("80M", 3.5, 4.0),
    ("40M", 7.0, 7.3),
    ("30M", 10.1, 10.15),
    ("20M", 14.0, 14.35),
    ("17M", 18.068, 18.168),
    ("15M", 21.0, 21.45),
    ("12M", 24.89, 24.99),
    ("10M", 28.0, 29.7),
]


@dataclass
class ClusterSpot:
    """Represents a cluster spot from RBN."""

    callsign: str
    frequency: float
    spotter: str
    time_utc: datetime
    snr: Optional[int] = None
    speed: Optional[int] = None  # WPM for CW
    comment: Optional[str] = None
    # Comma-separated list of club tags detected in the spot line, e.g. "SKCC, CWOPS, A1A"
    clubs: Optional[str] = None

    @property
    def band(self) -> str:
        """Calculate band from frequency."""
        for label, low, high in BAND_RANGES:
            if low <= self.frequency <= high:
                return label
        return "??M"

    def __str__(self):
        return (
            f"{self.callsign:>10} {self.frequency:>8.1f} {self.band:>4} "
            f"{self.spotter:>10} {self.time_utc.strftime('%H:%M')}"
        )


class SKCCClusterClient:
    """Client for CW club enriched RBN feed (rbn.telegraphy.de).

    Previous implementation forced SKCC-only filtering. This version allows
    requesting ALL clubs (default) or a narrowed list by passing a list of
    normalized club identifiers.

    If ``include_clubs`` is None (default) a "set/clubs all" command is sent.
    If it is a non-empty list, a comma separated list is sent (e.g.:
    "set/clubs skcc,cwops,a1a"). If the underlying gateway syntax differs,
    the user can set ``raw_clubs_command`` to override the automatic command
    construction entirely.
    """

    def __init__(
        self,
        callsign: str,
        spot_callback: Optional[Callable[[ClusterSpot], None]] = None,
        include_clubs: Optional[List[str]] = None,
        raw_clubs_command: Optional[str] = None,
        nodupes: bool = True,
    ):
        self.callsign = callsign.upper()
        self.spot_callback = spot_callback
        self.include_clubs = include_clubs
        self.raw_clubs_command = raw_clubs_command
        self.nodupes = nodupes
        self.connected = False
        self.socket = None
        self.thread = None
        self.running = False
        # RBN spot parsing regex
        # Example: DX de OH6BG-#:     7026.0  W4GNS          CQ      1322Z
        # Some gateways include additional text (e.g., club tags) between the call and time.
        self.spot_pattern = re.compile(r"DX de (\S+):\s+(\d+\.\d+)\s+(\S+).*?(\d{4})Z")

    def connect(self) -> bool:
        """Connect to the CW-Club RBN gateway."""
        try:
            print(f"Connecting to rbn.telegraphy.de:7000 as {self.callsign}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect(("rbn.telegraphy.de", 7000))

            # Send login first
            self._send_command(self.callsign)

            # Configure club filtering. Precedence:
            # 1. Explicit raw command if provided
            # 2. include_clubs list if provided (comma joined)
            # 3. "all" (default – show all available club annotations)
            try:
                if self.raw_clubs_command:
                    self._send_command(self.raw_clubs_command)
                elif self.include_clubs is None:
                    self._send_command("set/clubs all")
                else:
                    normalized = [c.strip().lower() for c in self.include_clubs if c.strip()]
                    if normalized:
                        self._send_command("set/clubs " + ",".join(normalized))
            except (OSError, ValueError):  # noqa: BLE001 - intentionally narrow and silent fallback
                pass

            # Reduce duplicates if requested
            if self.nodupes:
                self._send_command("set/nodupes")

            self.connected = True
            self.running = True

            # Start reading thread
            self.thread = threading.Thread(target=self._read_spots, daemon=True)
            self.thread.start()

            print("✅ Connected to SKCC cluster feed")
            return True

        except (OSError, TimeoutError) as e:
            print(f"❌ Failed to connect to cluster: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the cluster."""
        self.running = False
        self.connected = False

        if self.socket:
            with suppress(Exception):
                self.socket.close()
            self.socket = None

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        print("Disconnected from cluster")

    def _send_command(self, command: str):
        """Send a command to the cluster."""
        if self.socket:
            try:
                self.socket.send(f"{command}\r\n".encode())
            except OSError as e:
                print(f"Error sending command '{command}': {e}")

    def _read_spots(self):
        """Read spots from the cluster connection."""
        buffer = ""

        while self.running and self.connected:
            try:
                sock = self.socket
                if not sock:
                    break
                data = sock.recv(1024).decode("utf-8", errors="ignore")
                if not data:
                    break

                buffer += data
                lines = buffer.split("\n")
                buffer = lines[-1]  # Keep incomplete line

                for one in lines[:-1]:
                    line_stripped = one.strip()
                    if line_stripped:
                        self._process_line(line_stripped)

            except socket.timeout:
                continue
            except OSError as e:
                print(f"Error reading from cluster: {e}")
                break

        print("Cluster reading thread stopped")

    def _process_line(self, line: str):  # noqa: PLR0912 - complex parsing kept explicit for clarity
        """Process a line from the cluster."""
        # Look for DX spots
        match = self.spot_pattern.match(line)
        if match:
            try:
                spotter = match.group(1)
                frequency = float(match.group(2))
                callsign = match.group(3)
                time_str = match.group(4)

                # Parse time (HHMM format)
                hour = int(time_str[:2])
                minute = int(time_str[2:])

                # Create UTC time for today
                now = datetime.now(timezone.utc)
                spot_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # Handle day rollover
                if spot_time > now:
                    spot_time = spot_time.replace(day=spot_time.day - 1)

                # Extract SNR/speed if present in the line
                snr = None
                speed = None

                # Look for common RBN patterns
                if "dB" in line:
                    snr_match = re.search(r"(\d+)\s*dB", line)
                    if snr_match:
                        snr = int(snr_match.group(1))

                if "WPM" in line or "wpm" in line:
                    speed_match = re.search(r"(\d+)\s*[Ww][Pp][Mm]", line)
                    if speed_match:
                        speed = int(speed_match.group(1))

                # Extract club memberships mentioned in the spot line using
                # common synonyms/variants and normalize names.
                # This helps when gateways use different spellings (e.g. "CWops", "CW Ops").
                club_patterns: Dict[str, List[str]] = {
                    "SKCC": ["skcc"],
                    "CWOPS": ["cwops", "cw ops", "cw-ops", "cwo"],
                    "A1A": [
                        "a1a",
                        "a-1",
                        "a1-op",
                        "a1 op",
                        "a-1 op",
                        "arrl a-1",
                        "a1 operators",
                        "a-1 operators",
                    ],
                    "FISTS": ["fists"],
                    "NAQCC": ["naqcc"],
                    "FOC": ["foc"],
                    "AGCW": ["agcw"],
                    "HSC": ["hsc"],
                    "VHSC": ["vhsc"],
                    "EHSC": ["ehsc"],
                    # A few other frequent CW clubs that sometimes appear
                    "QRP-ARCI": ["qrparci", "qrp-arci", "qrp arci"],
                    "BUG": ["bug club"],  # rare tag
                }

                clubs_found_set: set[str] = set()
                lower_line = line.lower()

                # Try to extract from explicit key-value like `clubs: A1A,CWOPS`
                with suppress(Exception):
                    kv_match = re.search(r"clubs?[:=]\s*([A-Za-z0-9\- ,;/]+)", lower_line)
                    if kv_match:
                        raw = kv_match.group(1)
                        for token in re.split(r"[;,]", raw):
                            t = token.strip().lower()
                            if not t:
                                continue
                            for norm, pats in club_patterns.items():
                                if any(p in t for p in pats):
                                    clubs_found_set.add(norm)

                # Fallback: substring search across entire line
                for norm, pats in club_patterns.items():
                    if any(p in lower_line for p in pats):
                        clubs_found_set.add(norm)

                clubs_found: List[str] = sorted(clubs_found_set)
                clubs_text = ", ".join(clubs_found) if clubs_found else None

                # Create spot
                spot = ClusterSpot(
                    callsign=callsign,
                    frequency=frequency / 1000.0,  # Convert to MHz
                    spotter=spotter,
                    time_utc=spot_time,
                    snr=snr,
                    speed=speed,
                    clubs=clubs_text,
                )

                # Call callback if provided
                if self.spot_callback:
                    self.spot_callback(spot)

            except (ValueError, OSError) as e:
                print(f"Error parsing spot line '{line}': {e}")
        elif any(
            keyword in line.lower() for keyword in ["login", "welcome", "connected", "filter"]
        ):
            print(f"Cluster: {line}")

    def get_status(self) -> Dict[str, Any]:
        """Get connection status."""
        return {
            "connected": self.connected,
            "callsign": self.callsign,
            "running": self.running,
        }


# Example usage and testing
if __name__ == "__main__":

    def print_spot(spot: ClusterSpot):
        print(f"📡 {spot}")

    # Test connection (replace with your callsign)
    client = SKCCClusterClient("W4GNS-TEST", print_spot)

    if client.connect():
        try:
            print("Listening for SKCC spots... (Ctrl+C to exit)")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            client.disconnect()
    else:
        print("Failed to connect to cluster")
