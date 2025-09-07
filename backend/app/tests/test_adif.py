from app.services.skcc import parse_adif


def test_parse_single_record() -> None:
    adif = "<CALL:5>K1ABC<BAND:3>40M<MODE:2>CW<QSO_DATE:8>20240101<EOR>"
    qsos = parse_adif(adif)
    assert len(qsos) == 1
    q = qsos[0]
    assert q.call == "K1ABC"
    assert q.band == "40M"
    assert q.mode == "CW"
    assert q.date == "20240101"


def test_parse_multiple_with_header_and_missing_eor() -> None:
    adif = (
        "<EOH>"  # header end
        "<CALL:5>K1ABC<BAND:3>40M<MODE:2>CW<QSO_DATE:8>20240101<EOR>"
        "<CALL:6>WA9XYZ<BAND:3>20M<MODE:2>CW<QSO_DATE:8>20240102"  # no <EOR>
    )
    qsos = parse_adif(adif)
    assert len(qsos) == 2
    calls = {q.call for q in qsos}
    assert calls == {"K1ABC", "WA9XYZ"}


def test_parse_ignores_unknown_fields() -> None:
    adif = "<CALL:5>K1ABC<FOO:3>BAR<BAND:3>40M<MODE:2>CW<QSO_DATE:8>20240101<EOR>"
    qsos = parse_adif(adif)
    assert len(qsos) == 1
    assert qsos[0].call == "K1ABC"
