"""Pure, bounded time-series history helpers for the Min OK dashboard."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date

PERIODS = ("HOUR", "DAY", "MONTH", "QUARTER", "YEAR")
FIELDS = ("dato", "aflaest", "kwh", "dkk_inkl_moms", "dkk_ekskl_moms",
          "dkk_pr_kwh_inkl_moms", "dkk_pr_kwh_ekskl_moms",
          "kwh_gennemsnit_for_aar", "dkk_gennemsnit_for_aar_inkl_moms")
LIMITS = {"HOUR": 20000, "DAY": 2500, "MONTH": 120, "QUARTER": 60, "YEAR": 30}


def _clean_row(raw: Mapping) -> dict | None:
    """Only retain public graph fields, never customer IDs or API session data."""
    stamp = raw.get("dato")
    if not isinstance(stamp, str) or len(stamp) > 40:
        return None
    try:
        date.fromisoformat(stamp[:10])
    except ValueError:
        return None
    result = {"dato": stamp}
    if raw.get("aflaest") in (True, False):
        result["aflaest"] = raw["aflaest"]
    for field in FIELDS[2:]:
        value = raw.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[field] = round(float(value), 6)
        else:
            result[field] = None
    return result


def merge_rows(existing: list[dict], incoming: list[dict], period: str) -> list[dict]:
    """Deduplicate timestamped readings and retain an older real reading if
    a newer response has an unavailable placeholder. Real zeros remain zeros.
    """
    if period not in PERIODS:
        raise ValueError("Unsupported history period")
    indexed: dict[str, dict] = {}
    for source in (existing, incoming):
        for raw in source:
            if not isinstance(raw, Mapping) or (row := _clean_row(raw)) is None:
                continue
            key = row["dato"]
            old = indexed.get(key, {})
            if not old:
                indexed[key] = row
                continue
            merged = dict(old)
            for field in FIELDS[2:]:
                if row.get(field) is not None:
                    merged[field] = row[field]
            merged["aflaest"] = (
                bool(old.get("aflaest") or row.get("aflaest"))
                if "aflaest" in row or "aflaest" in old else None
            )
            indexed[key] = merged
    return [indexed[key] for key in sorted(indexed)[-LIMITS[period]:]]


def merge_history(
    existing: dict[str, list[dict]], incoming: dict[str, list[dict]]
) -> dict[str, list[dict]]:
    return {period: merge_rows(existing.get(period, []), incoming.get(period, []), period)
            for period in PERIODS}


def history_summary(history: dict[str, list[dict]]) -> dict[str, int]:
    return {period: len(history.get(period, [])) for period in PERIODS}
