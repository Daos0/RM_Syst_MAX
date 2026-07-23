from __future__ import annotations

import re


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold()).replace("ё", "е")
