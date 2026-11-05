"""Shared base entity for Dontek Aquatek."""
from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN, is_oasis
from .coordinator import DontekCoordinator


class DontekEntity(CoordinatorEntity[DontekCoordinator]):
    """Base entity tying everything to one controller device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        name = coordinator.entry.data.get(CONF_NAME, "Pool Pump")
        oasis = is_oasis(coordinator.data or {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac)},
            name=name,
            manufacturer="Dontek Electronics",
            model="Oasis pool controller" if oasis else "Aquatek pool controller",
            connections={(CONNECTION_NETWORK_MAC, format_mac(coordinator.mac))},
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.connected

    def reg(self, register: int) -> int | None:
        """Current value of a register, or None if not seen yet."""
        return (self.coordinator.data or {}).get(register)


def add_entities_live(
    entry: ConfigEntry,
    coordinator: DontekCoordinator,
    async_add_entities: AddEntitiesCallback,
    keys: Callable[[dict[int, int]], Iterable[Hashable]],
    make: Callable[[Hashable], Iterable[Entity]],
) -> None:
    """Add entities for each key now, and for new keys as later polls show them.

    keys(regs) lists what should have entities (e.g. the sockets present);
    make(key) builds them. Each key is added once, so an expansion socket or a
    light moved to another socket appears without a restart. Entities for keys
    that go away stay and report unavailable.
    """
    added: set[Hashable] = set()

    @callback
    def _add_new() -> None:
        new = [k for k in keys(coordinator.data or {}) if k not in added]
        if not new:
            return
        added.update(new)
        async_add_entities([e for k in new for e in make(k)])

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))
