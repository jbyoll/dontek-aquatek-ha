"""Sensors for Dontek Aquatek."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MODE_TO_STR,
    REG_PUMP_MODE,
    REG_PUMP_SPEED,
    REG_WATER_TEMP,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WaterTemperatureSensor(coordinator),
            PumpStatusSensor(coordinator),
            PumpSpeedSensor(coordinator),
        ]
    )


class WaterTemperatureSensor(DontekEntity, SensorEntity):
    """Pool water temperature (register 57545, Q8.8 fixed point)."""

    _attr_translation_key = "water_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_water_temp"

    @property
    def native_value(self) -> float | None:
        raw = self.reg(REG_WATER_TEMP)
        if raw is None:
            return None
        return round(raw / 256, 1)


class PumpStatusSensor(DontekEntity, SensorEntity):
    """Pump run mode as text (Off / On / Auto)."""

    _attr_translation_key = "pump_status"

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_status"

    @property
    def native_value(self) -> str | None:
        mode = self.reg(REG_PUMP_MODE)
        if mode is None:
            return None
        return MODE_TO_STR.get(mode, f"Unknown ({mode})")


class PumpSpeedSensor(DontekEntity, SensorEntity):
    """Currently selected pump speed (1-4)."""

    _attr_translation_key = "pump_speed"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_speed"

    @property
    def native_value(self) -> int | None:
        raw = self.reg(REG_PUMP_SPEED)
        if raw is None:
            return None
        return raw + 1  # register is zero-based
