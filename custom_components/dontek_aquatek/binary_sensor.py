"""Binary sensors for Dontek Aquatek (socket running flags, valves, Oasis solar pump)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_SOLAR_PUMP_ACTIVE,
    SOCKET_COUNT,
    SOCKET_RUNNING_UNASSIGNED,
    SOCKET_TYPE_NONE,
    is_oasis,
    VALVE_COUNT,
    socket_label,
    socket_present,
    socket_running_reg,
    socket_type_reg,
    valve_state_reg,
    valve_type_reg,
    valve_type_str,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    regs = coordinator.data or {}
    entities: list[DontekEntity] = [
        SocketRunningSensor(coordinator, socket)
        for socket in range(1, SOCKET_COUNT + 1)
        if socket_present(regs, socket) and socket_running_reg(socket) in regs
    ]
    for valve in range(1, VALVE_COUNT + 1):
        vtype = regs.get(valve_type_reg(valve))
        if vtype and valve_state_reg(valve) in regs:
            entities.append(ValveStateSensor(coordinator, valve))
    if is_oasis(regs):
        entities.append(SolarPumpRunningSensor(coordinator))
    async_add_entities(entities)


class SocketRunningSensor(DontekEntity, BinarySensorEntity):
    """Whether a socket is energised right now (register 160 + (n - 1)).

    0 = off, 1 = running, 2 = no appliance assigned (shown as unavailable).
    Named like the socket's mode select and follows renames.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: DontekCoordinator, socket: int) -> None:
        super().__init__(coordinator)
        self._socket = socket
        self._reg = socket_running_reg(socket)
        self._attr_unique_id = f"{coordinator.mac}_socket{socket}_running"
        stype = (coordinator.data or {}).get(socket_type_reg(socket))
        self._attr_entity_registry_enabled_default = stype != SOCKET_TYPE_NONE

    @property
    def name(self) -> str:
        return f"{socket_label(self.coordinator.data or {}, self._socket)} running"

    @property
    def available(self) -> bool:
        value = self.reg(self._reg)
        return super().available and value is not None and value != SOCKET_RUNNING_UNASSIGNED

    @property
    def is_on(self) -> bool | None:
        value = self.reg(self._reg)
        return None if value is None else value == 1


class ValveStateSensor(DontekEntity, BinarySensorEntity):
    """Live state of a valve the app has a function assigned to (168 + (n - 1)).

    Status only: the app can't move valves directly. On means the valve is in
    its switched position, e.g. a Pool/Spa valve reads on while in Spa mode.
    """

    def __init__(self, coordinator: DontekCoordinator, valve: int) -> None:
        super().__init__(coordinator)
        self._valve = valve
        self._reg = valve_state_reg(valve)
        self._attr_unique_id = f"{coordinator.mac}_valve{valve}"

    @property
    def name(self) -> str:
        vtype = valve_type_str(self.reg(valve_type_reg(self._valve)))
        return f"Valve {self._valve} {vtype}" if vtype else f"Valve {self._valve}"

    @property
    def available(self) -> bool:
        value = self.reg(self._reg)
        return super().available and value is not None and value != SOCKET_RUNNING_UNASSIGNED

    @property
    def is_on(self) -> bool | None:
        value = self.reg(self._reg)
        return None if value is None else value == 1

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        return {
            "valve": self._valve,
            "valve_type": valve_type_str(self.reg(valve_type_reg(self._valve))),
        }


class SolarPumpRunningSensor(DontekEntity, BinarySensorEntity):
    """Solar pump running flag on Oasis units (register 162).

    Created disabled: Oasis units without solar heating report the register too.
    """

    _attr_translation_key = "solar_pump"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_solar_pump"

    @property
    def is_on(self) -> bool | None:
        value = self.reg(REG_SOLAR_PUMP_ACTIVE)
        return None if value is None else value == 1
