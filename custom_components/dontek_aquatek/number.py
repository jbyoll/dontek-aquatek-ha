"""Number entities for Dontek Aquatek — per-speed power percentages."""
from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REG_SPEED_PCT
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        SpeedPercentNumber(coordinator, speed, reg)
        for speed, reg in REG_SPEED_PCT.items()
    ]
    entities.append(RunOnceMinutesNumber(coordinator))
    async_add_entities(entities)


class RunOnceMinutesNumber(DontekEntity, RestoreNumber):
    """How long the Run Once button runs the pump (stored in HA, not the device)."""

    _attr_translation_key = "run_once_minutes"
    _attr_native_min_value = 1
    _attr_native_max_value = 180
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-cog"

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_run_once_minutes"

    @property
    def available(self) -> bool:
        # a local setting — usable even if the cloud link is momentarily down
        return True

    @property
    def native_value(self) -> float | None:
        return self.coordinator.run_once_minutes

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.run_once_minutes = int(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        data = await self.async_get_last_number_data()
        if data is not None and data.native_value is not None:
            self.coordinator.run_once_minutes = int(data.native_value)


class SpeedPercentNumber(DontekEntity, NumberEntity):
    """Power percentage for one of the four pump speeds."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: DontekCoordinator, speed: int, reg: int) -> None:
        super().__init__(coordinator)
        self._speed = speed
        self._reg = reg
        self._attr_translation_key = f"speed_{speed}_pct"
        self._attr_unique_id = f"{coordinator.mac}_speed_{speed}_pct"

    @property
    def native_value(self) -> float | None:
        return self.reg(self._reg)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_register(self._reg, int(value))
