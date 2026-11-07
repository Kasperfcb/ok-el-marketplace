"""Pure calculations for Min OK sensor values; no Home Assistant dependency."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    values: dict[str, float | None]
    attributes: dict[str, dict[str, Any]]


def row_day(row: dict[str, Any]) -> date | None:
    """Get an ISO date from a row; ignore malformed records."""
    value = row.get("dato")
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def known_total(rows: list[dict[str, Any]], field: str) -> float | None:
    """Sum measured values, never interpreting an unavailable reading as zero."""
    values = [float(row[field]) for row in rows if
              isinstance(row.get(field), (int, float)) and
              not isinstance(row[field], bool)]
    return round(sum(values), 4) if values else None


def _pick(rows: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    valid = [row for row in rows if row_day(row) is not None
             and row.get(field) is not None
             and row.get("aflaest", True) is True]
    return max(valid, key=lambda r: str(r["dato"])) if valid else None


def _make_period(values: dict, attrs: dict, prefix: str,
                 rows: list[dict], start_label: str) -> None:
    values[prefix + "_kwh"] = known_total(rows, "kwh")
    values[prefix + "_cost"] = known_total(rows, "dkk_inkl_moms")
    measured = sum(row.get("kwh") is not None for row in rows)
    priced = sum(row.get("dkk_inkl_moms") is not None for row in rows)
    attributes = {"period": start_label, "measured_intervals": measured,
                  "priced_intervals": priced}
    attrs[prefix + "_kwh"] = attributes
    attrs[prefix + "_cost"] = attributes


def build_snapshot(
    *, today: date, daily: list[dict], hourly: list[dict],
    monthly: list[dict], quarterly: list[dict], annual: list[dict]
) -> Snapshot:
    """Build a noncumulative, measurement-only snapshot.

    Daily and hourly readings come from GetData. Month/quarter comparison
    aggregates are only used for current year and quarter. No synthetic
    lifetime meter/energy-dashboard counter is produced.
    """
    values: dict[str, float | None] = {}
    attrs: dict[str, dict[str, Any]] = {}

    measured_days = [r for r in daily if r.get("aflaest") is True
                     and r.get("kwh") is not None and row_day(r) is not None]
    latest_day = _pick(measured_days, "kwh")
    today_rows = [r for r in measured_days if row_day(r) == today]
    _make_period(values, attrs, "today", today_rows, today.isoformat())

    values["latest_day_kwh"] = (latest_day.get("kwh") if latest_day else None)
    values["latest_day_cost"] = (latest_day.get("dkk_inkl_moms") if latest_day else None)
    values["latest_day_price"] = (
        latest_day.get("dkk_pr_kwh_inkl_moms") if latest_day else None
    )
    for key in ("latest_day_kwh", "latest_day_cost", "latest_day_price"):
        attrs[key] = {"measurement_date": row_day(latest_day).isoformat()
                      if latest_day else None}

    measured_hours = [r for r in hourly if r.get("aflaest") is True
                      and r.get("kwh") is not None and row_day(r) is not None]
    latest_hour = _pick(measured_hours, "kwh")
    values["latest_hour_kwh"] = latest_hour.get("kwh") if latest_hour else None
    values["latest_hour_price"] = (
        latest_hour.get("dkk_pr_kwh_inkl_moms") if latest_hour else None
    )
    for key in ("latest_hour_kwh", "latest_hour_price"):
        attrs[key] = {"measurement_time": latest_hour.get("dato") if latest_hour else None}

    this_month = (today.year, today.month)
    prev_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    for prefix, target in (("current_month", this_month),
                           ("previous_month", prev_month)):
        records = [r for r in measured_days if
                   (row_day(r).year, row_day(r).month) == target]
        _make_period(values, attrs, prefix, records,
                     f"{target[0]}-{target[1]:02d}")

    current_quarter = (today.month - 1) // 3
    quarter_rows = [r for r in quarterly if row_day(r) is not None
                    and row_day(r).year == today.year
                    and (row_day(r).month - 1) // 3 == current_quarter]
    _make_period(values, attrs, "current_quarter", quarter_rows,
                 f"{today.year}-Q{current_quarter + 1}")

    year_months = [r for r in monthly if row_day(r) is not None
                   and row_day(r).year == today.year]
    _make_period(values, attrs, "current_year", year_months, str(today.year))

    previous_year_rows = [r for r in annual if row_day(r) is not None
                          and row_day(r).year == today.year - 1
                          and r.get("aflaest") is True]
    _make_period(values, attrs, "previous_year", previous_year_rows,
                 str(today.year - 1))

    return Snapshot(values=values, attributes=attrs)
