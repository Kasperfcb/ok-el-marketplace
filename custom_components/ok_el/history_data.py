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


def month_keys_from_rows(rows: list[dict]) -> set[str]:
    """Identify months already represented by a valid dated meter record."""
    keys = set()
    for row in rows:
        raw = row.get("dato") if isinstance(row, dict) else None
        if not isinstance(raw, str):
            continue
        try:
            stamp = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        keys.add(stamp.strftime("%Y-%m"))
    return keys


def missing_archive_months(
    requested: list[tuple[int, int]], today: date,
    saved_days: list[dict], successfully_checked: list[str],
) -> list[tuple[int, int]]:
    """Skip previously fetched or checked older months; refresh last 2 months.

    Rechecking the current/previous month allows late meter readings and
    corrections to arrive naturally without re-fetching entire archives.
    """
    recent = {today.strftime("%Y-%m")}
    if today.month == 1:
        recent.add(f"{today.year - 1}-12")
    else:
        recent.add(f"{today.year}-{today.month - 1:02d}")
    cached = month_keys_from_rows(saved_days) | set(successfully_checked)
    return [(year, month) for year, month in requested
            if f"{year}-{month:02d}" in recent
            or f"{year}-{month:02d}" not in cached]


def missing_hour_dates(
    measured_days: list[dict], saved_hours: list[dict], limit: int,
) -> list[str]:
    """Find newest available days not already cached with a full hour series."""
    if limit <= 0:
        return []
    days = sorted({
        row["dato"][:10] for row in measured_days
        if isinstance(row, dict) and isinstance(row.get("dato"), str)
        and row.get("aflaest") is True and row.get("kwh") is not None
    }, reverse=True)[:limit]
    coverage: dict[str, set[str]] = {}
    for row in saved_hours:
        stamp = row.get("dato") if isinstance(row, dict) else None
        if not isinstance(stamp, str) or len(stamp) < 13:
            continue
        if row.get("aflaest") is True and row.get("kwh") is not None:
            coverage.setdefault(stamp[:10], set()).add(stamp)
    # 23 covers daylight-saving spring dates; keep partial day windows eligible
    # for a later retry rather than treating no data as fully downloaded.
    return [day for day in days if len(coverage.get(day, set())) < 23]
