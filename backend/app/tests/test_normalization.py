from app.services.skcc import Member, QSO, calculate_awards


def test_call_normalization_aliases() -> None:
    members = [Member(call="K1ABC", number=101)]
    qsos = [
        QSO(call="K1ABC", band="40M", mode="CW", date="20240101"),
        QSO(call="K1ABC/QRP", band="40M", mode="CW", date="20240102"),
        QSO(call="DL/K1ABC", band="20M", mode="CW", date="20240103"),
        QSO(call="K1ABC/7", band="15M", mode="CW", date="20240104"),
    ]
    result = calculate_awards(qsos, members, thresholds=[("Mini", 1)])
    assert result.unique_members_worked == 1
    assert result.matched_qsos == 4
    assert result.unmatched_calls == []

