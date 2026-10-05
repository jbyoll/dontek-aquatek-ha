"""Switch entities for Dontek Aquatek (Filter Time enables, heater extras)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FILTER_TIME_COUNT,
    REG_FT_ENABLE_MASK,
    REG_HEATER_RUN_TIL_HEATED,
    REG_WATER_FEATURE,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[DontekEntity] = [
        FilterTimeEnableSwitch(coordinator, ft)
        for ft in range(1, FILTER_TIME_COUNT + 1)
    ]
    # optional features: only create them if the unit reports the register
    regs = coordinator.data or {}
    for reg, key, category in (
        # a setting, not a control: heater stops once at temperature
        (REG_HEATER_RUN_TIL_HEATED, "run_til_heated", EntityCategory.CONFIG),
        (REG_WATER_FEATURE, "water_feature", None),
    ):
        if reg in regs:
            entities.append(RegisterSwitch(coordinator, reg, key, category))
    async_add_entities(entities)


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


class RegisterSwitch(DontekEntity, SwitchEntity):
    """A plain 0/1 register (Run til heated 65500, Water Feature 65345)."""

    def __init__(
        self,
        coordinator: DontekCoordinator,
        reg: int,
        key: str,
        category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._reg = reg
        self._attr_entity_category = category
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.mac}_{key}"

    @property
    def is_on(self) -> bool | None:
        value = self.reg(self._reg)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(self._reg, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(self._reg, 0)
