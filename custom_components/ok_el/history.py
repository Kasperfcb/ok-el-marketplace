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
    missing_hour_dates, select_hour_dates, valid_hour_selection,
    HOUR_BATCH_SIZE, MAX_HOUR_DAYS,
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


def fetch_hour_batch(
    email: str, password: str, dates: list[str],
    progress: Callable[[int, int, str], None],
) -> tuple[list[dict], list[str], int]:
    """Fetch at most HOUR_BATCH_SIZE measured days with an independent session.

    A completed successful day's data is checkpointed by the manager; a failed
    request remains eligible when the user retries or the import resumes.
    """
    if not 0 < len(dates) <= HOUR_BATCH_SIZE:
        raise ValueError("Ugyldig timedataportion")
    client = OKClient()
    client.login(email, password)
    agreements = client.discover_agreement_numbers()
    if len(agreements) != 1:
        raise OKDataError("Kunne ikke finde én elaftale til timehistorik")
    agreement = agreements[0]
    rows: list[dict] = []
    checked: list[str] = []
    failed = 0
    for index, day in enumerate(dates, start=1):
        progress(index - 1, len(dates), f"Henter timeforbrug {day}")
        try:
            start, end = hour_window(date.fromisoformat(day))
            part = _pair(client, agreement, "HOUR", start, end)
            rows.extend(part)
            if any(r.get("aflaest") is True and r.get("kwh") is not None
                   for r in part):
                checked.append(day)
        except (OKAPIError, OKDataError, ValueError):
            failed += 1
        progress(index, len(dates), f"Timeforbrug {day}")
        time.sleep(0.25)
    return rows, checked, failed


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
        self.checked_hour_dates: list[str] = []
        self.pending_import: dict[str, Any] | None = None
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
            if isinstance(stored.get("checked_hour_dates"), list):
                self.checked_hour_dates = [
                    key for key in stored["checked_hour_dates"]
                    if isinstance(key, str) and len(key) == 10
                ]
            request = stored.get("pending_import")
            if (isinstance(request, dict)
                    and type(request.get("months")) is int
                    and 1 <= request["months"] <= 36
                    and valid_hour_selection(request.get("hour_days"))):
                self.pending_import = request

    async def _save(self) -> None:
        """Persist readings and import checkpoints to Home Assistant private storage."""
        await self.store.async_save({
            "history": self.rows,
            "last_completed": self.last_completed,
            "checked_months": self.checked_months,
            "checked_hour_dates": self.checked_hour_dates,
            "pending_import": self.pending_import,
        })

    async def async_ingest(self, incoming: dict[str, list[dict]]) -> None:
        """Merge new readings without losing past values and persist only changes."""
        updated = merge_history(self.rows, incoming)
        if updated != self.rows:
            self.rows = updated
            await self._save()

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
            "limits": {"months": 36, "hour_days": MAX_HOUR_DAYS, "all": True},
        }

    def start_backfill(self, months: int, hour_days: int | str) -> bool:
        """Start or resume a bounded, incremental background import."""
        if self.busy:
            return False
        if not 1 <= months <= 36 or not valid_hour_selection(hour_days):
            raise ValueError("Ugyldigt historikomfang")
        self.busy = True
        self.pending_import = {"months": months, "hour_days": hour_days}
        self.progress = {"completed": 0, "total": 0, "stage": "Starter import"}
        self.last_error = None
        self.hass.async_create_task(
            self._run_backfill(months, hour_days),
            f"ok_el_backfill_{self.entry.entry_id}",
        )
        return True

    def resume_pending(self) -> bool:
        """Resume an interrupted user-requested import after HA restarts."""
        pending = self.pending_import
        if not pending:
            return False
        return self.start_backfill(pending["months"], pending["hour_days"])

    def _update_progress(self, done: int, total: int, stage: str) -> None:
        """Run only on Home Assistant's event loop."""
        self.progress = {"completed": done, "total": total, "stage": stage}

    async def _run_backfill(self, months: int, hour_days: int | str) -> None:
        try:
            await self._save()  # Make the resume intent durable before any requests.
            current = {key: [dict(row) for row in value]
                       for key, value in self.rows.items()}
            def update_days(done: int, total: int, stage: str) -> None:
                self.hass.loop.call_soon_threadsafe(
                    self._update_progress, done, total, stage
                )
            # Fetch/refresh months first. Hourly data is fetched in small chunks
            # separately, rather than making 700+ requests inside one job.
            base = await self.hass.async_add_executor_job(
                fetch_archive,
                self.entry.data[CONF_EMAIL],
                self.entry.data[CONF_PASSWORD],
                months,
                0,
                current,
                list(self.checked_months),
                update_days,
            )
            failures = int(base.pop("_failed_count", 0))
            checked = base.pop("_checked_months", [])
            skipped_months = int(base.pop("_skipped_months", 0))
            base.pop("_skipped_hour_days", None)
            self.checked_months = sorted(set(self.checked_months) | set(checked))
            await self.async_ingest(base)
            await self._save()

            today = datetime.now(COPENHAGEN).date()
            scopes = previous_months(today, months)
            earliest_month = f"{scopes[-1][0]}-{scopes[-1][1]:02d}"
            remaining = select_hour_dates(
                self.rows.get("DAY", []), self.rows.get("HOUR", []), hour_days,
                earliest_month=earliest_month,
                checked_dates=self.checked_hour_dates,
            )
            total_days = len(remaining)
            imported_days = 0
            self.progress = {
                "completed": 0, "total": total_days,
                "stage": f"Genbruger {skipped_months} tidligere hentede måneder",
            }
            for offset in range(0, total_days, HOUR_BATCH_SIZE):
                chunk = remaining[offset:offset + HOUR_BATCH_SIZE]
                def update_hours(done: int, total: int, stage: str) -> None:
                    self.hass.loop.call_soon_threadsafe(
                        self._update_progress,
                        imported_days + done,
                        total_days,
                        stage,
                    )
                hour_rows, success_dates, failed_count = (
                    await self.hass.async_add_executor_job(
                        fetch_hour_batch,
                        self.entry.data[CONF_EMAIL],
                        self.entry.data[CONF_PASSWORD],
                        chunk,
                        update_hours,
                    )
                )
                failures += failed_count
                self.checked_hour_dates = sorted(
                    set(self.checked_hour_dates) | set(success_dates)
                )
                # Save after every batch. Already completed hours survive power
                # outages, cancellations and Home Assistant restarts.
                await self.async_ingest({"HOUR": hour_rows})
                imported_days += len(chunk)
                self.progress = {
                    "completed": imported_days, "total": total_days,
                    "stage": f"Gemte timedata til og med {chunk[-1]}",
                }
                await self._save()

            self.last_completed = datetime.now(COPENHAGEN).isoformat(
                timespec="seconds"
            )
            self.pending_import = None
            self.progress = {
                "completed": total_days, "total": total_days,
                "stage": f"Færdig – genbrugte {skipped_months} måneder",
            }
            if failures:
                self.last_error = (
                    f"Delvis import: {failures} forespørgsler mislykkedes. "
                    "Hentede data er gemt; prøv igen for manglende perioder."
                )
            await self._save()
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("OK El history import failed: %s", type(exc).__name__)
            self.last_error = (
                f"Historik kunne ikke hentes ({type(exc).__name__}). "
                "De allerede hentede målinger er bevaret."
            )
            self.progress = {
                "completed": 0, "total": 0,
                "stage": "Import afbrudt – fortsætter efter genstart eller næste forsøg",
            }
            # Keep the pending request so a restart can pick up from saved batches.
            await self._save()
        finally:
            self.busy = False
