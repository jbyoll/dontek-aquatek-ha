"""Time entities for Dontek Aquatek (Filter Time start/end for all schedules)."""
from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FILTER_TIMES, hm_to_reg, reg_to_hm
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[FilterTimeField] = []
    for ft, regs in FILTER_TIMES.items():
        entities.append(FilterTimeField(coordinator, f"filter{ft}_from", regs["from"]))
        entities.append(FilterTimeField(coordinator, f"filter{ft}_to", regs["to"]))
    async_add_entities(entities)


class FilterTimeField(DontekEntity, TimeEntity):
    """A single start/end time of a Filter Time (packed hour*256 + minute)."""

    def __init__(self, coordinator: DontekCoordinator, key: str, reg: int) -> None:
        super().__init__(coordinator)
        self._reg = reg
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.mac}_{key}"

    @property
    def native_value(self) -> dt_time | None:
        raw = self.reg(self._reg)
        if raw is None:
            return None
        hour, minute = reg_to_hm(raw)
        return dt_time(hour=hour, minute=minute)

    async def async_set_value(self, value: dt_time) -> None:
        await self.coordinator.async_write_register(
            self._reg, hm_to_reg(value.hour, value.minute)
        )
