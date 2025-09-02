from app.services import skcc


def test_special_calls_cutoff_behavior() -> None:
    members = [
        skcc.Member(call="K9SKC", number=1, join_date="20000101"),
        skcc.Member(call="K3Y/5", number=2, join_date="20000101"),
        skcc.Member(call="W1XYZ", number=3, join_date="20000101"),
    ]
    qsos = [
        # After cutoff date: K9SKC and K3Y/* should be excluded
        skcc.QSO(call="K9SKC", band="40M", mode="CW", date="20240101"),
        skcc.QSO(call="K3Y/5", band="20M", mode="CW", date="20240101"),
        skcc.QSO(call="W1XYZ", band="20M", mode="CW", date="20240101"),
    ]
    res = skcc.calculate_awards(qsos, members, thresholds=[("Centurion", 1)])
    assert res.unique_members_worked == 1
    assert res.unmatched_calls == []


def test_call_normalization_variants() -> None:
    members = [
        skcc.Member(call="K1ABC", number=10, join_date="20200101"),
    ]
    # Variants that should normalize to K1ABC
    qsos = [
        skcc.QSO(call="DL/K1ABC", band="20M", mode="CW", date="20240101"),
        skcc.QSO(call="K1ABC/7/P", band="20M", mode="CW", date="20240102"),
        skcc.QSO(call="K1ABC/QRP", band="20M", mode="CW", date="20240103"),
    ]
    res = skcc.calculate_awards(qsos, members, thresholds=[("Centurion", 1)])
    assert res.unique_members_worked == 1
