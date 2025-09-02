from app.services import skcc


def test_centurion_rule_filters() -> None:
    members = [
        skcc.Member(call="K1ABC", number=1, join_date="20240105"),  # join after first QSO
        skcc.Member(call="K3DEF", number=2, join_date="20240101"),
        skcc.Member(call="W1XYZ", number=3, join_date="20230101"),
        skcc.Member(
            call="K9SKC", number=4, join_date="20200101"
        ),  # disallowed special after cutoff
    ]
    qsos = [
        skcc.QSO(call="K1ABC", band="40M", mode="CW", date="20240101"),  # before join -> ignored
        skcc.QSO(call="K1ABC", band="40M", mode="CW", date="20240106"),  # counts
        skcc.QSO(call="K3DEF", band="20M", mode="CW", date="20240110"),  # counts
        skcc.QSO(call="K3Y/1", band="20M", mode="CW", date="20240110"),  # special event excluded
        skcc.QSO(call="K9SKC", band="80M", mode="CW", date="20240110"),  # club call excluded
        skcc.QSO(call="W1XYZ", band="15M", mode="CW", date="20230201"),  # counts
    ]
    result = skcc.calculate_awards(qsos, members, thresholds=[("Centurion", 100)])
    assert result.unique_members_worked == 3  # K1ABC, K3DEF, W1XYZ only
    # Ensure disallowed calls appear in unmatched if present
    assert "K9SKC" not in result.unmatched_calls  # excluded before unmatched tracking
    assert all(c not in result.unmatched_calls for c in ["K1ABC", "K3DEF", "W1XYZ"])  # matched
