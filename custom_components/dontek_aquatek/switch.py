"""Switch entities for Dontek Aquatek (schedule enable)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REG_FT1_ENABLE
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FilterTimeEnableSwitch(coordinator)])


class FilterTimeEnableSwitch(DontekEntity, SwitchEntity):
    """Enable/disable Filter Time 1 (register 65318)."""

    _attr_translation_key = "filter1_enabled"

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_filter1_enabled"

    @property
    def is_on(self) -> bool | None:
        val = self.reg(REG_FT1_ENABLE)
        if val is None:
            return None
        return val == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(REG_FT1_ENABLE, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(REG_FT1_ENABLE, 0)
