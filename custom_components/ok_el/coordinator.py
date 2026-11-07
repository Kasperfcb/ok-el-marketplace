"""Poll Min OK from a background worker; never block Home Assistant's event loop."""
from __future__ import annotations

from datetime import datetime
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import OKAPIError, OKClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, UPDATE_INTERVAL
from .dates import COPENHAGEN, hour_window, latest_metered_day, month_window, previous_months, year_window
from .metrics import Snapshot, build_snapshot
from .history import HistoryManager
from .normalize import OKDataError, normalize_comparison, normalize_intervals

_LOGGER = logging.getLogger(__name__)


def _both(client: OKClient, agreement: int, period: str,
          start: str, end: str) -> list[dict]:
    """Fetch separate kWh and currency displays; a currency value is never kWh."""
    power = client.get_data(
        agreement, period=period, start=start, end=end, display_type=0
    )
    time.sleep(0.2)
    prices = client.get_data(
        agreement, period=period, start=start, end=end, display_type=1
    )
    return normalize_intervals(power, prices, interval=period)


def fetch_snapshot(email: str, password: str) -> Snapshot:
    """Synchronous worker executed through hass.async_add_executor_job.

    An independent login per six-hour update avoids relying on saved cookies.
    Agreement IDs are discovered on the logged-in page, never hard-coded.
    """
    client = OKClient()
    client.login(email, password)

    candidates = client.discover_agreement_numbers()
    if len(candidates) != 1:
        raise OKDataError("OK returnerede ikke ét entydigt aftalenummer")
    agreement = candidates[0]
    today = datetime.now(COPENHAGEN).date()

    # Current and previous month, so dates around New Year are handled.
    daily: list[dict] = []
    for year, month in previous_months(today, 2):
        start, end = month_window(year, month)
        daily.extend(_both(client, agreement, "DAY", start, end))
        time.sleep(0.2)

    # OK frequently publishes readings 1-2 days late. Request the latest
    # *measured* day, not the present calendar date.
    hourly: list[dict] = []
    if any(row.get("aflaest") is True and row.get("kwh") is not None for row in daily):
        day = latest_metered_day(daily, today)
        start, end = hour_window(day)
        hourly = _both(client, agreement, "HOUR", start, end)
        time.sleep(0.2)

    monthly = normalize_comparison(
        client.get_comparison(
            agreement, period="MONTH", years=[today.year]
        ), period="MONTH",
    )
    time.sleep(0.2)
    quarterly = normalize_comparison(
        client.get_comparison(
            agreement, period="QUARTER", years=[today.year]
        ), period="QUARTER",
    )
    time.sleep(0.2)

    start, end = year_window(today.year - 1, today.year)
    annual = _both(client, agreement, "YEAR", start, end)

    return build_snapshot(
        today=today, daily=daily, hourly=hourly, monthly=monthly,
        quarterly=quarterly, annual=annual,
    )


class OKElCoordinator(DataUpdateCoordinator[Snapshot]):
    """Coordinate one slow refresh for all sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 history_manager: HistoryManager) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} ({entry.entry_id})",
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.entry = entry
        self.history_manager = history_manager

    async def _async_update_data(self) -> Snapshot:
        try:
            snapshot = await self.hass.async_add_executor_job(
                fetch_snapshot,
                self.entry.data[CONF_EMAIL],
                self.entry.data[CONF_PASSWORD],
            )
            await self.history_manager.async_ingest(snapshot.history)
            return snapshot
        except OKAPIError as exc:
            # Never include credentials, agreement ID or API response bodies.
            if "Login blev ikke godkendt" in str(exc):
                raise ConfigEntryAuthFailed("Min OK-login blev afvist") from exc
            raise UpdateFailed(str(exc)) from exc
        except (OKDataError, ValueError) as exc:
            raise UpdateFailed(str(exc)) from exc
