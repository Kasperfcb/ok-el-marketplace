"""Conservative extraction of agreement IDs from authenticated OK HTML.

Only explicitly labelled agreement fields are accepted. Never log page HTML:
it may contain personal or session information.
"""
from __future__ import annotations

from html import unescape
import re

_LABEL = r"(?:aftalenr|aftaleNr|aftaleNummer|aftalenummer|data-aftalenr|data-aftale-nr|data-aftale-nummer)"
_PATTERN = re.compile(
    r"(?<![\w-])(?:[\"']?" + _LABEL + r"[\"']?)\s*[:=]\s*[\"']?(\d{4,15})\b",
    re.IGNORECASE,
)


def find_agreement_numbers(html: str) -> list[int]:
    """Return unique explicitly labelled IDs or [] if no such field is present."""
    return sorted({int(match.group(1)) for match in _PATTERN.finditer(unescape(html))})
