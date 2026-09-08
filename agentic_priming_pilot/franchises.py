"""Franchise name fragments to exclude. Case-insensitive substring match
against the business name. Keep this list flat and easy to extend."""

FRANCHISE_EXCLUDE = [
    # tire chains
    "mavis",
    "discount tire",
    "firestone",
    "goodyear",
    "big o tires",
    "tire kingdom",
    "les schwab",
    "pep boys",
    "national tire",
    "ntb",
    "america's tire",
    "belle tire",
    "town fair tire",
    # body/collision chains
    "midas",
    "meineke",
    "caliber collision",
    "crash champions",
    "carstar",
    "abra auto",
    "gerber collision",
    "service king",
    "classic collision",
    "harley collision",
    "maaco",
    "fix auto",
    "safelite",
    "conicelli collision",
    "boyd group",
]


def is_franchise(name: str) -> bool:
    if not name:
        return False
    lowered = name.lower()
    return any(frag in lowered for frag in FRANCHISE_EXCLUDE)
