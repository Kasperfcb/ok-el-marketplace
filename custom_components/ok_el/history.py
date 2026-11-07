"""Local-only historical data cache and opt-in backfill from Min OK.

History lives in Home Assistant's private .storage, not sensor attributes,
GitHub, public HTTP paths or Recorder state changes.
"""
from __future__ import annotations

from datetime import date, datetime
import logging
import time
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .client import OKAPIError, OKClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .dates import COPENHAGEN, hour_window, month_window, previous_months, year_window
from .history_data import (
    PERIODS, history_summary, merge_history, missing_archive_months,
    missing_hour_dates,
)
from .normalize import OKDataError, normalize_comparison, normalize_intervals

_LOGGER = logging.getLogger(__name__)


def _pair(client: OKClient, agreement: int, period: str, start: str, end: str) -> list[dict]:
    """Fetch power and monetary readings separately to preserve their units."""
    power = client.get_data(agreement, period=period, start=start, end=end, display_type=0)
    time.sleep(0.2)
    money = client.get_data(agreement, period=period, start=start, end=end, display_type=1)
    return normalize_intervals(power, money, interval=period)


def fetch_archive(
    email: str, password: str, months: int, hour_days: int,
    saved: dict[str, list[dict]], checked_months: list[str],
    progress: Callable[[int, int, str], None],
) -> dict[str, list[dict]]:
    """Reuse private cached periods and fetch only missing history.

    Runs off the HA event loop. All URL requests remain sequential to be gentle
    with the unofficial OK API. Progress is forwarded thread-safely by caller.
    """
    if not 1 <= months <= 36 or not 0 <= hour_days <= 30:
        raise ValueError("Ugyldigt historikomfang")
    today = datetime.now(COPENHAGEN).date()
    months_to_fetch = previous_months(today, months)
    planned_months = missing_archive_months(
        months_to_fetch, today, saved.get("DAY", []), checked_months
    )
    years = sorted({year for year, _ in months_to_fetch})
    # The hour count is an upper bound until new daily readings arrive.
    total = len(planned_months) + hour_days + len(years) * 2 + 1
    completed = 0
    skipped = len(months_to_fetch) - len(planned_months)
    progress(completed, total, f"Genbruger {skipped} allerede hentede måneder")
    client = OKClient()
    client.login(email, password)
    candidates = client.discover_agreement_numbers()
    if len(candidates) != 1:
        raise OKDataError("Kan ikke finde præcis én elaftale hos OK")
    agreement = candidates[0]
    fetched: dict[str, list[dict]] = {period: [] for period in PERIODS}
    failures: list[str] = []
    checked_successfully = []

    for year, month in planned_months:
        start, end = month_window(year, month)
        label = f"{year}-{month:02d}"
        progress(completed, total, f"Henter dagsforbrug {label}")
        try:
            fetched["DAY"].extend(_pair(client, agreement, "DAY", start, end))
            checked_successfully.append(label)
        except (OKAPIError, OKDataError):
            failures.append(f"Dag {label}")
        completed += 1
        progress(completed, total, f"Dagsforbrug {label}")
        time.sleep(0.2)

    all_days = merge_history(saved, fetched)["DAY"]
    if not all_days:
        raise OKDataError("Ingen dagsdata kunne hentes eller genfindes fra OK")
    hour_dates = missing_hour_dates(
        all_days, saved.get("HOUR", []), hour_days
    )
    # Avoid reporting 30 remaining jobs if 7 days already exist locally.
    total = completed + len(hour_dates) + len(years) * 2 + 1
    for label in hour_dates:
        progress(completed, total, f"Henter timeforbrug {label}")
        start, end = hour_window(date.fromisoformat(label))
        try:
            fetched["HOUR"].extend(_pair(client, agreement, "HOUR", start, end))
        except (OKAPIError, OKDataError):
            failures.append(f"Time {label}")
        completed += 1
        progress(completed, total, f"Timeforbrug {label}")
        time.sleep(0.2)

    for year in years:
        progress(completed, total, f"Henter månedsoversigt {year}")
        try:
            fetched["MONTH"].extend(normalize_comparison(
                client.get_comparison(agreement, period="MONTH", years=[year]),
                period="MONTH",
            ))
        except (OKAPIError, OKDataError):
            failures.append(f"Måned {year}")
        completed += 1
        progress(completed, total, f"Månedsoversigt {year}")
        time.sleep(0.2)
        progress(completed, total, f"Henter kvartalsoversigt {year}")
        try:
            fetched["QUARTER"].extend(normalize_comparison(
                client.get_comparison(agreement, period="QUARTER", years=[year]),
                period="QUARTER",
            ))
        except (OKAPIError, OKDataError):
            failures.append(f"Kvartal {year}")
        completed += 1
        progress(completed, total, f"Kvartalsoversigt {year}")
        time.sleep(0.2)

    progress(completed, total, "Henter årsoversigt")
    start, end = year_window(years[0], years[-1])
    try:
        fetched["YEAR"] = _pair(client, agreement, "YEAR", start, end)
    except (OKAPIError, OKDataError):
        failures.append("Årsoversigt")
    completed += 1
    progress(completed, total, "Gemmer målinger lokalt")
    fetched["_failed_count"] = len(failures)
    fetched["_checked_months"] = checked_successfully
    fetched["_skipped_months"] = skipped
    fetched["_skipped_hour_days"] = max(0, hour_days - len(hour_dates))
    return fetched


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
        self.progress: dict[str, Any] = {"completed": 0, "total": 0, "stage": ""}
        self.checked_months: list[str] = []
        self.last_error: str | None = None
        self.last_completed: str | None = None

    async def async_load(self) -> None:
        """Read persisted data without fetching anything from OK."""
        stored = await self.store.async_load() or {}
        if isinstance(stored, dict) and isinstance(stored.get("history"), dict):
            self.rows = merge_history(self.rows, stored["history"])
            self.last_completed = stored.get("last_completed")
            if isinstance(stored.get("checked_months"), list):
                self.checked_months = [
                    key for key in stored["checked_months"]
                    if isinstance(key, str) and len(key) == 7
                ]

    async def async_ingest(self, incoming: dict[str, list[dict]]) -> None:
        """Merge new readings and save only when there was a change."""
        updated = merge_history(self.rows, incoming)
        if updated != self.rows:
            self.rows = updated
            await self.store.async_save({
                "history": self.rows,
                "last_completed": self.last_completed,
                "checked_months": self.checked_months,
            })

    def view(self, period: str) -> dict[str, Any]:
        if period not in PERIODS:
            raise ValueError("Ugyldig periode")
        return {
            "period": period,
            "rows": self.rows.get(period, []),
            "coverage": history_summary(self.rows),
            "busy": self.busy,
            "progress": self.progress,
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
        self.progress = {"completed": 0, "total": 0, "stage": "Starter import"}
        self.last_error = None
        self.hass.async_create_task(
            self._run_backfill(months, hour_days),
            f"ok_el_backfill_{self.entry.entry_id}",
        )
        return True

    def _update_progress(self, done: int, total: int, stage: str) -> None:
        """This callback must run in Home Assistant's event loop."""
        self.progress = {"completed": done, "total": total, "stage": stage}

    async def _run_backfill(self, months: int, hour_days: int) -> None:
        try:
            # Make a stable snapshot before sending any cached rows to a worker.
            current = {key: [dict(row) for row in value]
                       for key, value in self.rows.items()}
            def update(done: int, total: int, stage: str) -> None:
                self.hass.loop.call_soon_threadsafe(
                    self._update_progress, done, total, stage
                )
            history = await self.hass.async_add_executor_job(
                fetch_archive,
                self.entry.data[CONF_EMAIL],
                self.entry.data[CONF_PASSWORD],
                months,
                hour_days,
                current,
                list(self.checked_months),
                update,
            )
            missed = int(history.pop("_failed_count", 0))
            checked = history.pop("_checked_months", [])
            skipped_months = int(history.pop("_skipped_months", 0))
            skipped_hours = int(history.pop("_skipped_hour_days", 0))
            self.last_completed = datetime.now(COPENHAGEN).isoformat(timespec="seconds")
            self.checked_months = sorted(set(self.checked_months) | set(checked))
            await self.async_ingest(history)
            # Persist checked scopes even when all readings were already stored
            # or when the API returned empty historical periods.
            await self.store.async_save({
                "history": self.rows,
                "last_completed": self.last_completed,
                "checked_months": self.checked_months,
            })
            self.progress = {"completed": 1, "total": 1,
                             "stage": f"Færdig – genbrugte {skipped_months} måneder "
                                      f"og {skipped_hours} timedage"}
            if missed:
                self.last_error = (
                    f"Delvis import: {missed} dataforespørgsler kunne ikke hentes. "
                    "Allerede hentede målinger er gemt."
                )
        except Exception as exc:  # noqa: BLE001
            # Do not expose tokens, cookies or personal response bodies.
            _LOGGER.warning("OK El history import failed: %s", type(exc).__name__)
            self.last_error = f"Historik kunne ikke hentes ({type(exc).__name__}). Prøv igen."
            self.progress = {"completed": 0, "total": 0, "stage": "Import mislykkedes"}
        finally:
            self.busy = False
