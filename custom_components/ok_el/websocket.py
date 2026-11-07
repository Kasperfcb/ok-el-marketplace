"""Authenticated, admin-only WebSocket data for the OK El dashboard.

Never exposes email, passwords, agreement IDs, session cookies or HTTP responses.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .history import HistoryManager


def _manager(hass: HomeAssistant, entry_id: str | None) -> HistoryManager | None:
    entries: dict[str, HistoryManager] = hass.data.get(DOMAIN, {}).get("entries", {})
    if entry_id:
        return entries.get(entry_id)
    return next(iter(entries.values())) if len(entries) == 1 else None


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ok_el/history",
        vol.Optional("entry_id"): str,
        vol.Optional("period", default="DAY"): vol.In(["HOUR", "DAY", "MONTH", "QUARTER", "YEAR"]),
    }
)
@callback
def ws_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return bounded, personally stored time series only to a HA admin."""
    manager = _manager(hass, msg.get("entry_id"))
    if manager is None:
        connection.send_error(msg["id"], "not_found", "No unique OK El account found")
        return
    connection.send_result(msg["id"], manager.view(msg["period"]))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ok_el/backfill",
        vol.Optional("entry_id"): str,
        vol.Optional("months", default=12): vol.All(vol.Coerce(int), vol.Range(min=1, max=36)),
        vol.Optional("hour_days", default=7): vol.All(vol.Coerce(int), vol.Range(min=0, max=30)),
    }
)
@callback
def ws_backfill(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Start an explicitly requested, rate-limited history import."""
    manager = _manager(hass, msg.get("entry_id"))
    if manager is None:
        connection.send_error(msg["id"], "not_found", "No unique OK El account found")
        return
    started = manager.start_backfill(msg["months"], msg["hour_days"])
    connection.send_result(msg["id"], {"started": started, "busy": manager.busy})


def register_websocket_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_history)
    websocket_api.async_register_command(hass, ws_backfill)
