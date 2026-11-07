"""Read-only sensors populated by one shared Min OK coordinator."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OKElCoordinator


def _energy(key: str, name: str) -> SensorEntityDescription:
    return SensorEntityDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        # Period totals are snapshots, not a continuously increasing meter.
        suggested_display_precision=2,
    )


def _money(key: str, name: str) -> SensorEntityDescription:
    return SensorEntityDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="DKK",
        # Period totals are snapshots, not a continuously increasing meter.
        suggested_display_precision=2,
    )


def _unitprice(key: str, name: str) -> SensorEntityDescription:
    return SensorEntityDescription(
        key=key,
        name=name,
        native_unit_of_measurement="DKK/kWh",
        # The reported price is for a historical reading, not a live measurement.
        suggested_display_precision=3,
    )


SENSORS = (
    _energy("today_kwh", "Forbrug i dag"),
    _money("today_cost", "Pris i dag"),
    _energy("latest_day_kwh", "Seneste aflæste dag – forbrug"),
    _money("latest_day_cost", "Seneste aflæste dag – pris"),
    _unitprice("latest_day_price", "Seneste aflæste dag – gennemsnitspris"),
    _energy("latest_hour_kwh", "Seneste aflæste time – forbrug"),
    _unitprice("latest_hour_price", "Seneste aflæste time – pris pr. kWh"),
    _energy("current_month_kwh", "Forbrug denne måned"),
    _money("current_month_cost", "Pris denne måned"),
    SensorEntityDescription(
        key="current_month_measured_days",
        name="Aflæste dage denne måned",
        native_unit_of_measurement="dage",
        suggested_display_precision=0,
    ),
    _energy("last_7_days_kwh", "Forbrug de seneste 7 afsluttede dage"),
    _money("last_7_days_cost", "Pris de seneste 7 afsluttede dage"),
    _energy("day_1_kwh", "Forbrug i går"),
    _money("day_1_cost", "Pris i går"),
    _energy("day_2_kwh", "Forbrug i forgårs"),
    _money("day_2_cost", "Pris i forgårs"),
    _energy("day_3_kwh", "Forbrug for 3 dage siden"),
    _money("day_3_cost", "Pris for 3 dage siden"),
    _energy("day_4_kwh", "Forbrug for 4 dage siden"),
    _money("day_4_cost", "Pris for 4 dage siden"),
    _energy("day_5_kwh", "Forbrug for 5 dage siden"),
    _money("day_5_cost", "Pris for 5 dage siden"),
    _energy("day_6_kwh", "Forbrug for 6 dage siden"),
    _money("day_6_cost", "Pris for 6 dage siden"),
    _energy("day_7_kwh", "Forbrug for 7 dage siden"),
    _money("day_7_cost", "Pris for 7 dage siden"),
    _energy("previous_month_kwh", "Forbrug sidste måned"),
    _money("previous_month_cost", "Pris sidste måned"),
    _energy("current_quarter_kwh", "Forbrug dette kvartal"),
    _money("current_quarter_cost", "Pris dette kvartal"),
    _energy("current_year_kwh", "Forbrug i år (registrerede måneder)"),
    _money("current_year_cost", "Pris i år (registrerede måneder)"),
    _energy("previous_year_kwh", "Forbrug sidste år"),
    _money("previous_year_cost", "Pris sidste år"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Install stable, uniquely identified sensors."""
    coordinator: OKElCoordinator = entry.runtime_data
    async_add_entities(OKElSensor(coordinator, entry, description) for description in SENSORS)


class OKElSensor(CoordinatorEntity[OKElCoordinator], SensorEntity):
    """One read-only measurement from the shared latest snapshot."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OKElCoordinator,
        entry: ConfigEntry, description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        account_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{account_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name="Min OK El",
            manufacturer="OK",
            model="Elforbrug (uofficielt web-API)",
            configuration_url="https://www.ok.dk/min-ok-forside",
        )

    @property
    def name(self) -> str | None:
        """Show the correct Danish weekday/date, while keeping stable entity IDs.

        day_1/day_2 etc. remain the same registry entities as dates advance.
        """
        key = self.entity_description.key
        if key.startswith("day_") and (key.endswith("_kwh") or key.endswith("_cost")):
            details = self.coordinator.data.attributes.get(key, {})
            label = details.get("date_label")
            if isinstance(label, str):
                kind = "Forbrug" if key.endswith("_kwh") else "Pris"
                order = int(key.split("_")[1])
                return f"{kind} – {order:02d} – {label}"
        return self.entity_description.name

    @property
    def native_value(self) -> float | None:
        """Return the measured value or None; never manufacture a zero."""
        return self.coordinator.data.values.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict:
        """Only non-sensitive dates and coverage counts."""
        return self.coordinator.data.attributes.get(self.entity_description.key, {})
