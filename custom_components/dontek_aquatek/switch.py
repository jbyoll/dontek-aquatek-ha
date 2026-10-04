"""Switch entities for Dontek Aquatek (Filter Time enables)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FILTER_TIME_COUNT, REG_FT_ENABLE_MASK
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FilterTimeEnableSwitch(coordinator, ft)
        for ft in range(1, FILTER_TIME_COUNT + 1)
    )


class FilterTimeEnableSwitch(DontekEntity, SwitchEntity):
    """Enable/disable one Filter Time via a bit of the enable mask (reg 65318)."""

    def __init__(self, coordinator: DontekCoordinator, ft: int) -> None:
        super().__init__(coordinator)
        self._ft = ft
        self._bit = 1 << (ft - 1)
        self._attr_translation_key = f"filter{ft}_enabled"
        self._attr_unique_id = f"{coordinator.mac}_filter{ft}_enabled"

    @property
    def is_on(self) -> bool | None:
        mask = self.reg(REG_FT_ENABLE_MASK)
        if mask is None:
            return None
        return bool(mask & self._bit)

    async def async_turn_on(self, **kwargs: Any) -> None:
        mask = self.reg(REG_FT_ENABLE_MASK) or 0
        await self.coordinator.async_write_register(
            REG_FT_ENABLE_MASK, (mask | self._bit) & 0xFFFF
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        mask = self.reg(REG_FT_ENABLE_MASK) or 0
        await self.coordinator.async_write_register(
            REG_FT_ENABLE_MASK, mask & ~self._bit & 0xFFFF
        )
