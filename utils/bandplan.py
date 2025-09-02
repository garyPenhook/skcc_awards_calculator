from typing import Optional

# Minimal HF coverage; extend as needed
_BANDS = [
    (1.8, 2.0, "160M"),
    (3.5, 4.0, "80M"),
    (5.2, 5.5, "60M"),
    (7.0, 7.3, "40M"),
    (10.1, 10.15, "30M"),
    (14.0, 14.35, "20M"),
    (18.068, 18.168, "17M"),
    (21.0, 21.45, "15M"),
    (24.89, 24.99, "12M"),
    (28.0, 29.7, "10M"),
]


def freq_to_band(mhz: float) -> Optional[str]:
    for lo, hi, name in _BANDS:
        if lo <= mhz <= hi:
            return name
    return None
