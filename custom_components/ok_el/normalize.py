"""Normalize Min OK JSON into HA-friendly records.

Display type 0 means kWh; type 1 represents monetary values.
Never mistake the type-1 'forbrug' field for electricity in kWh.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class OKDataError(ValueError):
    pass


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _price(value: Any, field: str = "priceIncludingVat") -> float | None:
    return _num(value.get(field)) if isinstance(value, dict) else None


def normalize_intervals(kwh_response: Any, money_response: Any, *, interval: str) -> list[dict[str, Any]]:
    if not isinstance(kwh_response, list) or not isinstance(money_response, list):
        raise OKDataError("Forventede to lister fra GetData")

    def index(records: list[Any], name: str) -> dict[str, dict]:
        indexed: dict[str, dict] = {}
        for row in records:
            if not isinstance(row, dict) or not isinstance(row.get("dato"), str):
                raise OKDataError(f"Uventet element i {name}")
            indexed[row["dato"]] = row
        return indexed

    power = index(kwh_response, "kWh")
    prices = index(money_response, "priser")
    rows = []
    for key in sorted(set(power) | set(prices)):
        p, m = power.get(key, {}), prices.get(key, {})
        read = p.get("aflaest") is True
        money_read = m.get("aflaest") is True
        rows.append({
            "dato": key,
            "periode": interval,
            "aflaest": read,
            "kwh": _num(p.get("forbrug")) if read else None,
            "dkk_inkl_moms": _price(m.get("totalConsumptionPrice")) if money_read else None,
            "dkk_ekskl_moms": _price(m.get("totalConsumptionPrice"), "price") if money_read else None,
            "dkk_pr_kwh_inkl_moms": _price(m.get("pricePerKiloWattHour")) if money_read else None,
            "dkk_pr_kwh_ekskl_moms": _price(m.get("pricePerKiloWattHour"), "price") if money_read else None,
        })
    return rows


def normalize_comparison(response: Any, *, period: str) -> list[dict[str, Any]]:
    if not isinstance(response, list):
        raise OKDataError("GetDataComparison skulle returnere en liste")
    rows = []
    for group in response:
        if not isinstance(group, dict) or not isinstance(group.get("consumption"), list):
            raise OKDataError("Uventet år i GetDataComparison")
        for item in group["consumption"]:
            if not isinstance(item, dict):
                continue
            power = item.get("powerConsumption")
            money = item.get("monetaryConsumption")
            valid_power = isinstance(power, dict) and power.get("powerConsumptionToShow") is True
            valid_money = (isinstance(money, dict) and money.get("monetaryConsumptionToShow") is True
                           and item.get("monetaryConsumptionToShow") is not False)
            rows.append({
                "aar": group.get("year"),
                "dato": item.get("dato"),
                "periode": item.get("periode") or period,
                "kwh": _num(power.get("consumption")) if valid_power else None,
                "dkk_inkl_moms": _price(money.get("totalConsumptionPrice")) if valid_money else None,
                "dkk_ekskl_moms": _price(money.get("totalConsumptionPrice"), "price") if valid_money else None,
                "dkk_pr_kwh_inkl_moms": _price(money.get("pricePerKiloWattHour")) if valid_money else None,
                "dkk_pr_kwh_ekskl_moms": _price(money.get("pricePerKiloWattHour"), "price") if valid_money else None,
                "kwh_gennemsnit_for_aar": _num(group.get("powerConsumptionAverage")),
                "dkk_gennemsnit_for_aar_inkl_moms": _price(group.get("monetaryConsumptionAverage")),
            })
    return sorted(rows, key=lambda r: (str(r["aar"]), str(r["dato"])))


def normalize_invoices(response: Any) -> list[dict[str, Any]]:
    """Parser only. Invoice endpoint needs dynamic session-dependent ?k= token."""
    if not isinstance(response, dict) or not isinstance(response.get("rows"), list):
        raise OKDataError("GetFakturaRows skulle returnere {rows: [...]}.")
    out = []
    for item in response["rows"]:
        if isinstance(item, dict):
            out.append({
                "dato": item.get("dato"),
                "info": item.get("info"),
                "beloeb": _num(item.get("beloeb")),
                "saldo": _num(item.get("saldo")),
                "fakturanr": item.get("fakturanr"),
            })
    return out


def coverage_statistics(rows: list[Mapping]) -> dict[str, Any]:
    return {
        "antal": len(rows),
        "aflaeste_intervaller": sum(x.get("aflaest") is True for x in rows),
        "kwh_punkter": sum(x.get("kwh") is not None for x in rows),
        "pris_punkter": sum(x.get("dkk_inkl_moms") is not None for x in rows),
    }
