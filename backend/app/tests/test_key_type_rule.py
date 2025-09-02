from app.services import skcc


def test_key_type_enforcement_defaults() -> None:
    members = [
        skcc.Member(call="K1AAA", number=1, join_date="20240101"),
        skcc.Member(call="K1BBB", number=2, join_date="20240101"),
        skcc.Member(call="K1CCC", number=3, join_date="20240101"),
    ]
    qsos = [
        skcc.QSO(
            call="K1AAA",
            band="40M",
            mode="CW",
            date="20240102",
            key_type="Straight Key",
        ),  # allowed
        skcc.QSO(call="K1BBB", band="40M", mode="CW", date="20240102", key_type="Bug"),  # allowed
        skcc.QSO(
            call="K1CCC",
            band="40M",
            mode="CW",
            date="20240102",
            key_type="Iambic Paddle",
        ),  # disallowed
        skcc.QSO(
            call="K1CCC", band="40M", mode="CW", date="20240103"
        ),  # missing key (counts when treat_missing_key_as_valid)
    ]
    result = skcc.calculate_awards(
        qsos,
        members,
        thresholds=[("Centurion", 2)],
        enforce_key_type=True,
        treat_missing_key_as_valid=True,
    )
    assert result.unique_members_worked == 3  # K1AAA,K1BBB (allowed) + K1CCC via missing key QSO


def test_key_type_enforcement_strict_missing_not_allowed() -> None:
    members = [
        skcc.Member(call="K1AAA", number=1, join_date="20240101"),
        skcc.Member(call="K1BBB", number=2, join_date="20240101"),
        skcc.Member(call="K1CCC", number=3, join_date="20240101"),
    ]
    qsos = [
        skcc.QSO(
            call="K1AAA", band="40M", mode="CW", date="20240102", key_type="Straight"
        ),  # allowed
        skcc.QSO(
            call="K1BBB", band="40M", mode="CW", date="20240102", key_type="Paddle"
        ),  # disallowed
        skcc.QSO(
            call="K1CCC", band="40M", mode="CW", date="20240102"
        ),  # missing key -> disallowed in strict mode
    ]
    result = skcc.calculate_awards(
        qsos,
        members,
        thresholds=[("Centurion", 2)],
        enforce_key_type=True,
        treat_missing_key_as_valid=False,
    )
    assert result.unique_members_worked == 1  # Only K1AAA counts
