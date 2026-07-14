import json
from functools import lru_cache
from pathlib import Path

DEFAULT_COLLECTION_ICON = "folder"

SUGGESTED_COLLECTION_ICONS = [
    "folder",
    "folder-outline",
    "folder-star",
    "bookmark",
    "heart",
    "star",
    "gift",
    "toy-brick",
    "puzzle",
    "gamepad-variant",
    "tools",
    "hammer-wrench",
    "wrench",
    "screwdriver",
    "hammer",
    "home",
    "sofa",
    "lamp",
    "flower",
    "tree",
    "car",
    "airplane",
    "rocket",
    "robot",
    "printer-3d",
    "cube-outline",
    "shape",
    "palette",
    "brush",
    "pencil",
    "school",
    "briefcase",
    "medical-bag",
    "food",
    "cup",
    "paw",
    "cat",
    "dog",
    "account-group",
    "baby-carriage",
]

# Backwards-compatible alias used in templates and context processors.
COLLECTION_ICONS = SUGGESTED_COLLECTION_ICONS

_MDI_ICONS_PATH = Path(__file__).resolve().parent / "data" / "mdi-icons.json"


@lru_cache(maxsize=1)
def mdi_icon_names() -> frozenset[str]:
    with _MDI_ICONS_PATH.open(encoding="utf-8") as handle:
        icons = json.load(handle)
    return frozenset(icons)


def is_valid_collection_icon(name: str) -> bool:
    return name in mdi_icon_names()
