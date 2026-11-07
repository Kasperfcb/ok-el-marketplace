"""Danish local-time date ranges matching the captured Min OK requests."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

COPENHAGEN = ZoneInfo("Europe/Copenhagen")


def utc_stamp(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def month_window(y: int, m: int) -> tuple[str, str]:
    """Start of a month through the last day at 00:00; observed in browser capture."""
    if not 1 <= m <= 12:
        raise ValueError("Ugyldig måned")
    first = datetime(y, m, 1, tzinfo=COPENHAGEN)
    last = datetime(y, m, calendar.monthrange(y, m)[1], tzinfo=COPENHAGEN)
    return utc_stamp(first), utc_stamp(last)


def hour_window(day: date) -> tuple[str, str]:
    """Local 00:00 through 23:00, with local DST conversion."""
    first = datetime.combine(day, time(0), tzinfo=COPENHAGEN)
    last = datetime.combine(day, time(23), tzinfo=COPENHAGEN)
    return utc_stamp(first), utc_stamp(last)


def year_window(start_year: int, end_year: int) -> tuple[str, str]:
    return (utc_stamp(datetime(start_year, 1, 1, tzinfo=COPENHAGEN)),
            utc_stamp(datetime(end_year, 12, 31, tzinfo=COPENHAGEN)))


def previous_months(now: date, count: int) -> list[tuple[int, int]]:
    result = []
    for k in range(count):
        idx = now.year * 12 + now.month - 1 - k
        y, m = divmod(idx, 12)
        result.append((y, m + 1))
    return result


def latest_metered_day(rows: list[dict], fallback: date) -> date:
    """Pick the latest day with an actual meter reading, never a placeholder zero."""
    available: list[date] = []
    for row in rows:
        if row.get("aflaest") is not True or row.get("kwh") is None:
            continue
        raw_date = row.get("dato")
        if not isinstance(raw_date, str):
            continue
        try:
            parsed = date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        if parsed <= fallback:
            available.append(parsed)
    return max(available, default=fallback)
