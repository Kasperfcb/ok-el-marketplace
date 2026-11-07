"""Local-only historical data cache and opt-in backfill from Min OK.

History lives in Home Assistant's private .storage, not sensor attributes,
GitHub, public HTTP paths or Recorder state changes.
"""
from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .client import OKAPIError, OKClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .dates import COPENHAGEN, hour_window, month_window, previous_months, year_window
from .history_data import PERIODS, history_summary, merge_history
from .normalize import OKDataError, normalize_comparison, normalize_intervals

_LOGGER = logging.getLogger(__name__)


def _pair(client: OKClient, agreement: int, period: str, start: str, end: str) -> list[dict]:
    """Fetch power and monetary readings separately to preserve their units."""
    power = client.get_data(agreement, period=period, start=start, end=end, display_type=0)
    time.sleep(0.2)
    money = client.get_data(agreement, period=period, start=start, end=end, display_type=1)
    return normalize_intervals(power, money, interval=period)


def fetch_archive(email: str, password: str, months: int, hour_days: int) -> dict[str, list[dict]]:
    """Synchronous, explicitly requested historical export (runs in HA executor).

    At most 36 months of daily data and 30 measured days of hourly data per job.
    No invoice numbers or other account information are exported.
    """
    if not 1 <= months <= 36 or not 0 <= hour_days <= 30:
        raise ValueError("Ugyldigt historikomfang")
    today = datetime.now(COPENHAGEN).date()
    client = OKClient()
    client.login(email, password)
    candidates = client.discover_agreement_numbers()
    if len(candidates) != 1:
        raise OKDataError("Kan ikke finde præcis én elaftale hos OK")
    agreement = candidates[0]

    days: list[dict] = []
    failures: list[str] = []
    months_to_fetch = previous_months(today, months)
    for year, month in months_to_fetch:
        start, end = month_window(year, month)
        try:
            days.extend(_pair(client, agreement, "DAY", start, end))
        except (OKAPIError, OKDataError):
            failures.append(f"Dag {year}-{month:02d}")
        time.sleep(0.35)
    if not days:
        raise OKDataError("Ingen dagsdata kunne hentes fra OK")

    hours: list[dict] = []
    available = sorted({
        item["dato"][:10] for item in days
        if item.get("aflaest") is True and item.get("kwh") is not None
        and isinstance(item.get("dato"), str)
        and item["dato"][:10] <= today.isoformat()
    }, reverse=True)[:hour_days]
    from datetime import date
    for label in available:
        start, end = hour_window(date.fromisoformat(label))
        try:
            hours.extend(_pair(client, agreement, "HOUR", start, end))
        except (OKAPIError, OKDataError):
            failures.append(f"Time {label}")
        time.sleep(0.35)

    years = sorted({year for year, _ in months_to_fetch})
    monthly: list[dict] = []
    quarterly: list[dict] = []
    for year in years:
        try:
            monthly.extend(normalize_comparison(
                client.get_comparison(agreement, period="MONTH", years=[year]), period="MONTH"
            ))
        except (OKAPIError, OKDataError):
            failures.append(f"Måned {year}")
        time.sleep(0.35)
        try:
            quarterly.extend(normalize_comparison(
                client.get_comparison(agreement, period="QUARTER", years=[year]), period="QUARTER"
            ))
        except (OKAPIError, OKDataError):
            failures.append(f"Kvartal {year}")
        time.sleep(0.35)

    start, end = year_window(years[0], years[-1])
    try:
        annual = _pair(client, agreement, "YEAR", start, end)
    except (OKAPIError, OKDataError):
        annual = []
        failures.append("Årsoversigt")
    return {"HOUR": hours, "DAY": days, "MONTH": monthly,
            "QUARTER": quarterly, "YEAR": annual, "_failed_count": len(failures)}


class HistoryManager:
    """Persistent personal history shared by sensors and the dashboard."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.history.{entry.entry_id}",
            private=True, serialize_in_event_loop=False,
        )
        self.rows: dict[str, list[dict]] = {period: [] for period in PERIODS}
        self.busy = False
        self.last_error: str | None = None
        self.last_completed: str | None = None

    async def async_load(self) -> None:
        """Read persisted data without fetching anything from OK."""
        stored = await self.store.async_load() or {}
        if isinstance(stored, dict) and isinstance(stored.get("history"), dict):
            self.rows = merge_history(self.rows, stored["history"])
            self.last_completed = stored.get("last_completed")

    async def async_ingest(self, incoming: dict[str, list[dict]]) -> None:
        """Merge new readings and save only when there was a change."""
        updated = merge_history(self.rows, incoming)
        if updated != self.rows:
            self.rows = updated
            await self.store.async_save({
                "history": self.rows,
                "last_completed": self.last_completed,
            })

    def view(self, period: str) -> dict[str, Any]:
        if period not in PERIODS:
            raise ValueError("Ugyldig periode")
        return {
            "period": period,
            "rows": self.rows.get(period, []),
            "coverage": history_summary(self.rows),
            "busy": self.busy,
            "last_error": self.last_error,
            "last_completed": self.last_completed,
            "limits": {"months": 36, "hour_days": 30},
        }

    def start_backfill(self, months: int, hour_days: int) -> bool:
        """Start background job; never block the browser WebSocket connection."""
        if self.busy:
            return False
        if not 1 <= months <= 36 or not 0 <= hour_days <= 30:
            raise ValueError("Ugyldigt historikomfang")
        self.busy = True
        self.last_error = None
        self.hass.async_create_task(
            self._run_backfill(months, hour_days),
            f"ok_el_backfill_{self.entry.entry_id}",
        )
        return True

    async def _run_backfill(self, months: int, hour_days: int) -> None:
        try:
            history = await self.hass.async_add_executor_job(
                fetch_archive,
                self.entry.data[CONF_EMAIL],
                self.entry.data[CONF_PASSWORD],
                months,
                hour_days,
            )
            self.last_completed = datetime.now(COPENHAGEN).isoformat(timespec="seconds")
            missed = int(history.pop("_failed_count", 0))
            await self.async_ingest(history)
            if missed:
                self.last_error = (
                    f"Delvis import: {missed} dataforespørgsler kunne ikke hentes. "
                    "Allerede hentede målinger er gemt."
                )
        except Exception as exc:  # noqa: BLE001
            # Do not expose tokens, cookies or personal response bodies.
            _LOGGER.warning("OK El history import failed: %s", type(exc).__name__)
            self.last_error = f"Historik kunne ikke hentes ({type(exc).__name__}). Prøv igen."
        finally:
            self.busy = False
