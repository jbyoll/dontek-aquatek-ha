"""Select entities for Dontek Aquatek (pump mode and speed)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FILTER_TIMES,
    MODE_TO_STR,
    REG_PUMP_MODE,
    REG_PUMP_SPEED,
    SPEED_COUNT,
    STR_TO_MODE,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[DontekEntity] = [
        PumpModeSelect(coordinator),
        PumpSpeedSelect(coordinator),
    ]
    for ft, regs in FILTER_TIMES.items():
        entities.append(FilterTimeSpeedSelect(coordinator, ft, regs["speed"]))
    async_add_entities(entities)


class PumpModeSelect(DontekEntity, SelectEntity):
    """Off / On / Auto run mode (register 65485)."""

    _attr_translation_key = "pump_mode"
    _attr_options = ["Off", "On", "Auto"]

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_mode"

    @property
    def current_option(self) -> str | None:
        mode = self.reg(REG_PUMP_MODE)
        if mode is None:
            return None
        return MODE_TO_STR.get(mode)

    async def async_select_option(self, option: str) -> None:
        value = STR_TO_MODE.get(option)
        if value is None:
            return
        await self.coordinator.async_write_register(REG_PUMP_MODE, value)


class PumpSpeedSelect(DontekEntity, SelectEntity):
    """Manual speed selector 1-4 (register 65463, zero-based)."""

    _attr_translation_key = "pump_speed_select"
    _attr_options = [str(i) for i in range(1, SPEED_COUNT + 1)]

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_speed_select"

    @property
    def current_option(self) -> str | None:
        raw = self.reg(REG_PUMP_SPEED)
        if raw is None:
            return None
        return str(raw + 1)

    async def async_select_option(self, option: str) -> None:
        try:
            speed = int(option)
        except ValueError:
            return
        await self.coordinator.async_write_register(REG_PUMP_SPEED, speed - 1)


class FilterTimeSpeedSelect(DontekEntity, SelectEntity):
    """Speed used by a Filter Time schedule (zero-based register, 0-3 -> Speed 1-4)."""

    _attr_options = [str(i) for i in range(1, SPEED_COUNT + 1)]

    def __init__(self, coordinator: DontekCoordinator, ft: int, reg: int) -> None:
        super().__init__(coordinator)
        self._reg = reg
        self._attr_translation_key = f"filter{ft}_speed"
        self._attr_unique_id = f"{coordinator.mac}_filter{ft}_speed"

    @property
    def current_option(self) -> str | None:
        raw = self.reg(self._reg)
        if raw is None:
            return None
        return str(raw + 1)

    async def async_select_option(self, option: str) -> None:
        try:
            speed = int(option)
        except ValueError:
            return
        await self.coordinator.async_write_register(self._reg, speed - 1)
