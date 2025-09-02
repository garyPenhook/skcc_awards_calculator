from enum import Enum


class KeyType(str, Enum):
    STRAIGHT = "straight"
    BUG = "bug"
    SIDESWIPER = "sideswiper"  # cootie


DISPLAY_LABELS = {
    KeyType.STRAIGHT: "Straight key",
    KeyType.BUG: "Bug",
    KeyType.SIDESWIPER: "Side swiper",
}

SYNONYMS = {
    "straight": KeyType.STRAIGHT,
    "sk": KeyType.STRAIGHT,
    "bug": KeyType.BUG,
    "ss": KeyType.SIDESWIPER,
    "cootie": KeyType.SIDESWIPER,
    "side swiper": KeyType.SIDESWIPER,
    "sideswiper": KeyType.SIDESWIPER,
}


def normalize(value: str) -> KeyType:
    if not value:
        raise ValueError("key type required")
    t = value.strip().lower()
    if t in SYNONYMS:
        return SYNONYMS[t]
    for k, label in DISPLAY_LABELS.items():
        if t == label.lower():
            return k
    raise ValueError(f"unknown key type: {value}")
