"""Button entities for Dontek Aquatek (Run Once one-shot)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RunOnceButton(coordinator)])


class RunOnceButton(DontekEntity, ButtonEntity):
    """Start a one-shot pump run for the configured duration, now."""

    _attr_translation_key = "run_once"
    _attr_icon = "mdi:timer-play"

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_run_once"

    async def async_press(self) -> None:
        await self.coordinator.async_run_once(self.coordinator.run_once_minutes)
