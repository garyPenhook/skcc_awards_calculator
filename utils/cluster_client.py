#!/usr/bin/env python3
"""SKCC Cluster Spot Manager - Connects to CW-Club RBN Gateway for SKCC-filtered spots."""

import socket
import threading
import time
import re
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass


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

    @property
    def band(self) -> str:
        """Calculate band from frequency."""
        if 1.8 <= self.frequency <= 2.0:
            return "160M"
        elif 3.5 <= self.frequency <= 4.0:
            return "80M"
        elif 7.0 <= self.frequency <= 7.3:
            return "40M"
        elif 10.1 <= self.frequency <= 10.15:
            return "30M"
        elif 14.0 <= self.frequency <= 14.35:
            return "20M"
        elif 18.068 <= self.frequency <= 18.168:
            return "17M"
        elif 21.0 <= self.frequency <= 21.45:
            return "15M"
        elif 24.89 <= self.frequency <= 24.99:
            return "12M"
        elif 28.0 <= self.frequency <= 29.7:
            return "10M"
        else:
            return "??M"

    def __str__(self):
        return f"{self.callsign:>10} {self.frequency:>8.1f} {self.band:>4} {self.spotter:>10} {self.time_utc.strftime('%H:%M')}"


class SKCCClusterClient:
    """Connects to rbn.telegraphy.de for SKCC-filtered cluster spots."""

    def __init__(
        self,
        callsign: str,
        spot_callback: Optional[Callable[[ClusterSpot], None]] = None,
    ):
        self.callsign = callsign.upper()
        self.spot_callback = spot_callback
        self.connected = False
        self.socket = None
        self.thread = None
        self.running = False

        # RBN spot parsing regex
        # Example: DX de OH6BG-#:     7026.0  W4GNS          CQ      1322Z
        self.spot_pattern = re.compile(r"DX de (\S+):\s+(\d+\.\d+)\s+(\S+)\s+.*?(\d{4})Z")

    def connect(self) -> bool:
        """Connect to the CW-Club RBN gateway."""
        try:
            print(f"Connecting to rbn.telegraphy.de:7000 as {self.callsign}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect(("rbn.telegraphy.de", 7000))

            # Send login
            self._send_command(self.callsign)

            # Set up filtering for SKCC only
            self._send_command("set/clubs")  # Enable club filtering
            self._send_command("set/nodupes")  # Reduce duplicates

            self.connected = True
            self.running = True

            # Start reading thread
            self.thread = threading.Thread(target=self._read_spots, daemon=True)
            self.thread.start()

            print("✅ Connected to SKCC cluster feed")
            return True

        except Exception as e:
            print(f"❌ Failed to connect to cluster: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the cluster."""
        self.running = False
        self.connected = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        print("Disconnected from cluster")

    def _send_command(self, command: str):
        """Send a command to the cluster."""
        if self.socket:
            try:
                self.socket.send(f"{command}\r\n".encode("utf-8"))
            except Exception as e:
                print(f"Error sending command '{command}': {e}")

    def _read_spots(self):
        """Read spots from the cluster connection."""
        buffer = ""

        while self.running and self.connected:
            try:
                data = self.socket.recv(1024).decode("utf-8", errors="ignore")
                if not data:
                    break

                buffer += data
                lines = buffer.split("\n")
                buffer = lines[-1]  # Keep incomplete line

                for line in lines[:-1]:
                    line = line.strip()
                    if line:
                        self._process_line(line)

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error reading from cluster: {e}")
                break

        print("Cluster reading thread stopped")

    def _process_line(self, line: str):
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

                # Create spot
                spot = ClusterSpot(
                    callsign=callsign,
                    frequency=frequency / 1000.0,  # Convert to MHz
                    spotter=spotter,
                    time_utc=spot_time,
                    snr=snr,
                    speed=speed,
                )

                # Call callback if provided
                if self.spot_callback:
                    self.spot_callback(spot)

            except Exception as e:
                print(f"Error parsing spot line '{line}': {e}")
        else:
            # Print non-spot lines for debugging (login messages, etc.)
            if any(
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
