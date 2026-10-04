"""Number entities for Dontek Aquatek — per-speed power percentages."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REG_SPEED_PCT
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SpeedPercentNumber(coordinator, speed, reg)
        for speed, reg in REG_SPEED_PCT.items()
    )


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
