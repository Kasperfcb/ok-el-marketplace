"""Offline regression tests for automatic Home Assistant dashboard resource registration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "ok_el" / "frontend_registration.py"


@dataclass
class FakeStaticPathConfig:
    url_path: str
    path: str
    cache_headers: bool


class FakeCoreState:
    running = "running"


class FakeResources:
    def __init__(self, stored=None):
        self.loaded = False
        self.existing = list(stored or [])
        self.items = []
        self.loads = 0

    async def async_load(self):
        self.items = [dict(item) for item in self.existing]
        self.loaded = True
        self.loads += 1

    def async_items(self):
        if not self.loaded:
            raise AssertionError("Resources must be loaded before reading")
        return list(self.items)

    async def async_create_item(self, data):
        if not self.loaded:
            raise AssertionError("Cannot create without loading persisted resources")
        self.items.append({"id": str(len(self.items) + 1), **data})

    async def async_update_item(self, item_id, data):
        for item in self.items:
            if item["id"] == item_id:
                item.update(data)
                return
        raise AssertionError("Resource ID not found")


class FakeHTTP:
    def __init__(self):
        self.paths = []

    async def async_register_static_paths(self, paths):
        self.paths.extend(paths)


class FakeHomeAssistant:
    def __init__(self, mode, resources):
        self.http = FakeHTTP()
        self.data = {"lovelace": types.SimpleNamespace(
            resource_mode=mode, resources=resources
        )}
        self.state = FakeCoreState.running

    @property
    def bus(self):
        raise AssertionError("Already running; must not register a startup listener")


def load_module():
    """Provide minimal HA APIs without installing Home Assistant in CI."""
    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    http = types.ModuleType("homeassistant.components.http")
    http.StaticPathConfig = FakeStaticPathConfig
    core = types.ModuleType("homeassistant.core")
    core.CoreState = FakeCoreState
    core.EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"
    core.HomeAssistant = FakeHomeAssistant
    modules = {
        "homeassistant": ha,
        "homeassistant.components": components,
        "homeassistant.components.http": http,
        "homeassistant.core": core,
    }
    return modules


class CardResourceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.patcher = patch.dict(sys.modules, load_module())
        self.patcher.start()
        spec = importlib.util.spec_from_file_location("ok_el_frontend_reg_test", SOURCE)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_auto_registers_with_current_resource_mode_api(self):
        resources = FakeResources([{
            "id": "other", "url": "/local/existing-card.js", "res_type": "module"
        }])
        hass = FakeHomeAssistant("storage", resources)
        await self.mod.async_register_card(hass)
        self.assertEqual(resources.loads, 1)
        self.assertEqual(len(resources.items), 2)
        self.assertEqual(resources.items[0]["url"], "/local/existing-card.js")
        registered = resources.items[1]
        self.assertEqual(registered["res_type"], "module")
        self.assertIn("/ok-el-assets/ok-el-history-card.js?v=", registered["url"])
        self.assertEqual(hass.http.paths[0].url_path, "/ok-el-assets/ok-el-history-card.js")
        self.assertIsInstance(hass.http.paths[0].path, str)
        self.assertTrue(Path(hass.http.paths[0].path).is_file())

    async def test_updates_old_url_without_duplicate(self):
        resources = FakeResources([{
            "id": "ok", "url": "/ok-el-assets/ok-el-history-card.js?v=0.2.0",
            "res_type": "module"
        }])
        hass = FakeHomeAssistant("storage", resources)
        await self.mod.async_register_card(hass)
        self.assertEqual(len(resources.items), 1)
        self.assertIn("?v=0.2.1", resources.items[0]["url"])

    async def test_does_not_modify_yaml_resources(self):
        resources = FakeResources()
        hass = FakeHomeAssistant("yaml", resources)
        await self.mod.async_register_card(hass)
        self.assertFalse(resources.loaded)
        self.assertEqual(len(hass.http.paths), 1)


if __name__ == "__main__":
    unittest.main()
