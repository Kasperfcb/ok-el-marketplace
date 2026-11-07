"""Serve the dashboard card and register it in Lovelace storage mode.

Only JavaScript is public at /ok-el-assets; private meter data is always
returned separately through authenticated, admin-only Home Assistant WebSockets.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import CoreState, EVENT_HOMEASSISTANT_STARTED, HomeAssistant

_LOGGER = logging.getLogger(__name__)
BASE_URL = "/ok-el-assets"
JS_PATH = Path(__file__).parent / "frontend" / "ok-el-history-card.js"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve bundled JavaScript and register a dashboard resource if supported."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(BASE_URL + "/ok-el-history-card.js", JS_PATH, False)
    ])

    async def _register_resource() -> None:
        lovelace = hass.data.get("lovelace")
        # Home Assistant stores the resource configuration mode in
        # LovelaceData.resource_mode (not .mode).  The old check caused the
        # integration to skip registration on otherwise working installations.
        if lovelace is None or getattr(lovelace, "resource_mode", None) != "storage":
            _LOGGER.info(
                "OK El history card can be added manually as a module resource at %s",
                BASE_URL + "/ok-el-history-card.js",
            )
            return
        try:
            resources = lovelace.resources
            # Never create a resource before loading existing resources.
            # Older HA versions could otherwise overwrite the user's resources.
            if not resources.loaded:
                await resources.async_load()
            version = json.loads(
                (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
            )["version"]
            path = BASE_URL + "/ok-el-history-card.js"
            url = path + "?v=" + version
            existing = next(
                (item for item in resources.async_items()
                 if item.get("url", "").split("?")[0] == path),
                None,
            )
            if existing is None:
                await resources.async_create_item({"res_type": "module", "url": url})
                _LOGGER.info("Registered OK El dashboard card at %s", url)
            elif existing.get("url") != url:
                await resources.async_update_item(
                    existing["id"], {"res_type": "module", "url": url}
                )
                _LOGGER.info("Updated OK El dashboard card to %s", url)
        except Exception:  # noqa: BLE001
            # The integration and sensors must remain usable even if a dashboard
            # uses YAML resource mode or frontend APIs change in later HA versions.
            _LOGGER.warning(
                "OK El could not auto-register the dashboard resource. "
                "Add /ok-el-assets/ok-el-history-card.js as JavaScript module."
            )

    if hass.state is CoreState.running:
        await _register_resource()
    else:
        async def _on_started(_event) -> None:
            await _register_resource()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
