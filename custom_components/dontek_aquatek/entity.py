"""Shared base entity for Dontek Aquatek."""
from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN
from .coordinator import DontekCoordinator


class DontekEntity(CoordinatorEntity[DontekCoordinator]):
    """Base entity tying everything to one controller device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        name = coordinator.entry.data.get(CONF_NAME, "Pool Pump")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac)},
            name=name,
            manufacturer="Dontek Electronics",
            model="Aquatek pool controller",
            connections={(CONNECTION_NETWORK_MAC, format_mac(coordinator.mac))},
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.connected

    def reg(self, register: int) -> int | None:
        """Current value of a register, or None if not seen yet."""
        return (self.coordinator.data or {}).get(register)
