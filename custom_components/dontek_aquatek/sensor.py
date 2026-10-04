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
    REG_RUN_STATE,
    REG_WATER_TEMP,
    RUN_STATE,
    RUN_STATE_RUNNING,
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
            PumpActivitySensor(coordinator),
            RunningSpeedSensor(coordinator),
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


class PumpActivitySensor(DontekEntity, SensorEntity):
    """What the pump is doing right now (Running / Priming / Idle / ...)."""

    _attr_translation_key = "pump_activity"

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_activity"

    @property
    def native_value(self) -> str | None:
        word = self.reg(REG_RUN_STATE)
        if word is None:
            return None
        state = (word >> 8) & 0xFF
        return RUN_STATE.get(state, "Idle")


class RunningSpeedSensor(DontekEntity, SensorEntity):
    """The speed the pump is actually running at right now (1-4).

    This reflects the live filter schedule and can differ from the set speed
    while in Auto mode. It is only meaningful while the pump is running.
    """

    _attr_translation_key = "running_speed"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_running_speed"

    @property
    def native_value(self) -> int | None:
        word = self.reg(REG_RUN_STATE)
        if word is None:
            return None
        state = (word >> 8) & 0xFF
        if state != RUN_STATE_RUNNING:
            return None  # not running -> no meaningful speed
        return (word & 0xFF) + 1  # low byte is 0-based
