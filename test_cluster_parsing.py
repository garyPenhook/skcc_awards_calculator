from utils.cluster_client import ClusterSpot, SKCCClusterClient

TOL = 1e-6


def test_process_line_parses_clubs_and_band():
    captured: list[ClusterSpot] = []

    def _cb(spot: ClusterSpot):
        captured.append(spot)

    client = SKCCClusterClient("W4GNS-TEST", _cb)

    # Simulate a typical cluster line including club mentions and time.
    # Format expected by regex: "DX de <spotter>: <freq>  <callsign> ... <HHMM>Z"
    line = "DX de OH6BG-#:     7026.0  W4GNS   CQ CQ SKCC, CWops, A1A  1322Z"

    client._process_line(line)  # noqa: SLF001 - intentionally testing internal parser

    assert len(captured) == 1
    spot = captured[0]

    # Frequency is parsed in kHz and divided by 1000.0 to MHz
    assert abs(spot.frequency - 7.026) < TOL
    assert spot.callsign == "W4GNS"
    assert spot.band == "40M"

    # Clubs should include normalized CWOPS and SKCC, A1A
    assert spot.clubs is not None
    assert "SKCC" in spot.clubs
    assert "CWOPS" in spot.clubs  # "CWops" should normalize to "CWOPS"
    assert "A1A" in spot.clubs
