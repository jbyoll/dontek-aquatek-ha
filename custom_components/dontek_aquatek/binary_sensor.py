"""Binary sensors for Dontek Aquatek (Oasis solar pump)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REG_SOLAR_PUMP_ACTIVE, is_oasis
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    if is_oasis(coordinator.data or {}):
        async_add_entities([SolarPumpRunningSensor(coordinator)])


class SolarPumpRunningSensor(DontekEntity, BinarySensorEntity):
    """Solar pump running flag on Oasis units (register 162).

    Created disabled: Oasis units without solar heating report the register too.
    """

    _attr_translation_key = "solar_pump"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_solar_pump"

    @property
    def is_on(self) -> bool | None:
        value = self.reg(REG_SOLAR_PUMP_ACTIVE)
        return None if value is None else value == 1
