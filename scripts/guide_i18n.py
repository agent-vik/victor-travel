#!/usr/bin/env python3
"""Shared bilingual labels and section keys for guide render/docx."""

from __future__ import annotations

SECTION_KEYS = {
    "itinerary": ("行程", "Itinerary"),
    "checklist": ("检查清单", "Checklist"),
    "tips": ("小提示", "Tips"),
    "pois": ("候选景点", "POI Shortlist"),
}

SECTION_ALIASES: dict[str, str] = {}
for key, (zh, en) in SECTION_KEYS.items():
    SECTION_ALIASES[zh] = key
    SECTION_ALIASES[en] = key

UI = {
    "zh": {
        "day_nav": "每日行程",
        "poi_ref": "参考原点：",
        "accommodation": "住宿",
    },
    "en": {
        "day_nav": "Daily plan",
        "poi_ref": "Reference point: ",
        "accommodation": "Accommodation",
    },
}


def section_key(title: str) -> str | None:
    return SECTION_ALIASES.get(title.strip())


def section_title(key: str, lang: str) -> str:
    zh, en = SECTION_KEYS[key]
    return en if lang == "en" else zh
