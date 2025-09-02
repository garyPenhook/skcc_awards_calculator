from typing import List, Tuple

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.routes import awards as awards_route
from app.main import app
from app.services import skcc


@pytest.mark.asyncio
async def test_calculate_awards_simple() -> None:
    members = [skcc.Member(call="K1ABC", number=1), skcc.Member(call="WA9XYZ", number=2)]
    qsos = [
        skcc.QSO(call="K1ABC", band="40M", mode="CW", date="20240101"),
        skcc.QSO(call="K1ABC", band="40M", mode="CW", date="20240102"),  # duplicate member
        skcc.QSO(call="WA9XYZ", band="20M", mode="CW", date="20240103"),
    ]
    result = skcc.calculate_awards(qsos, members, thresholds=[("Mini", 1)], enable_endorsements=True)
    assert result.unique_members_worked == 2
    assert any(e.category == "band" for e in result.endorsements)
    assert any(e.category == "mode" for e in result.endorsements)

@pytest.mark.asyncio
async def test_awards_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    # Monkeypatch roster fetch in the awards route namespace (the symbol actually used by endpoint)
    async def fake_fetch_roster() -> List[skcc.Member]:
        return [
            skcc.Member(call="K1ABC", number=10),
            skcc.Member(call="WA9XYZ", number=11),
            skcc.Member(call="N0CALL", number=12),
        ]
    monkeypatch.setattr(awards_route, "fetch_member_roster", fake_fetch_roster)

    async def fake_fetch_thresholds() -> List[Tuple[str, int]]:
        return [("Centurion", 1), ("Tribune", 2)]
    monkeypatch.setattr(awards_route, "fetch_award_thresholds", fake_fetch_thresholds)

    adif = (
        "<CALL:5>K1ABC<BAND:3>40M<MODE:2>CW<QSO_DATE:8>20240101<EOR>"
        "<CALL:6>WA9XYZ<BAND:3>20M<MODE:2>CW<QSO_DATE:8>20240102<EOR>"
        "<CALL:6>WA9XYZ<BAND:3>20M<MODE:2>CW<QSO_DATE:8>20240103<EOR>"  # duplicate QSO
    )
    files = {"files": ("log.adi", adif, "text/plain")}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/awards/check", files=files)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["unique_members_worked"] == 2
    cent = next(a for a in data["awards"] if a["name"] == "Centurion")
    assert cent["achieved"] is True
    endorsements = data.get("endorsements", [])
    assert endorsements
    values = {(e["award"], e["category"], e["value"]) for e in endorsements}
    assert ("Centurion", "band", "40M") in values
    assert ("Centurion", "band", "20M") in values
    assert ("Centurion", "mode", "CW") in values
    assert ("Tribune", "mode", "CW") in values
