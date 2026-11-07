"""Home Assistant integration for OK electricity, prices and private history."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import OKElCoordinator
from .frontend_registration import async_register_card
from .history import HistoryManager
from .websocket import register_websocket_commands


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register authenticated historical data and a bundled Lovelace resource."""
    hass.data.setdefault(DOMAIN, {"entries": {}})
    register_websocket_commands(hass)
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OK El without reauthentication or changing existing entity IDs."""
    manager = HistoryManager(hass, entry)
    await manager.async_load()
    coordinator = OKElCoordinator(hass, entry, manager)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {"entries": {}})["entries"][entry.entry_id] = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Resume only an import the account owner previously requested.
    manager.resume_pending()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload sensors; preserve historical readings and saved login."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        hass.data.get(DOMAIN, {}).get("entries", {}).pop(entry.entry_id, None)
    return result
