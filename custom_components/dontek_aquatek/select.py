"""Select entities for Dontek Aquatek (pump, sockets, pool/spa)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FILTER_TIMES,
    FP_MODE_TO_STR,
    FP_STR_TO_MODE,
    POOL_SPA_STR_TO_MODE,
    POOL_SPA_TO_STR,
    REG_FILTER_PUMP_MODE,
    REG_POOL_SPA_MODE,
    REG_PUMP_MODE,
    REG_PUMP_SPEED,
    REG_SPA_ENABLED,
    SOCKET_COUNT,
    SOCKET_TYPE_NONE,
    SOCKET_TYPES,
    SOCKET_TYPES_LIGHT,
    SPEED_COUNT,
    STR_TO_MODE,
    is_oasis,
    light_colour_reg,
    light_colour_str,
    light_colour_value,
    light_colours,
    light_sockets,
    light_type,
    light_type_mapped,
    pump_mode_str,
    socket_controllable,
    socket_label,
    socket_mode_reg,
    socket_name,
    socket_present,
    socket_type_reg,
    socket_type_str,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity, add_entities_live


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[DontekEntity] = [
        PumpModeSelect(coordinator),
        PumpSpeedSelect(coordinator),
        FilterPumpModeSelect(coordinator),
    ]
    for ft, regs in FILTER_TIMES.items():
        entities.append(FilterTimeSpeedSelect(coordinator, ft, regs["speed"]))
    regs = coordinator.data or {}
    if REG_POOL_SPA_MODE in regs:
        entities.append(PoolSpaModeSelect(coordinator))
    async_add_entities(entities)

    def _socket_selects(socket: int) -> list[DontekEntity]:
        # Socket 1's mode is the Filter Pump select above.
        if socket == 1:
            return [SocketTypeSelect(coordinator, socket)]
        return [SocketTypeSelect(coordinator, socket), SocketModeSelect(coordinator, socket)]

    # Sockets (incl. expansion sockets fitted later) and lights (incl. one
    # moved to another socket) are picked up on the next poll, no restart.
    add_entities_live(
        entry,
        coordinator,
        async_add_entities,
        lambda regs: [s for s in range(1, SOCKET_COUNT + 1) if socket_present(regs, s)],
        _socket_selects,
    )
    add_entities_live(
        entry,
        coordinator,
        async_add_entities,
        lambda regs: [("light", s) for s in light_sockets(regs)],
        lambda key: [LightColourSelect(coordinator, key[1])],
    )


class PumpModeSelect(DontekEntity, SelectEntity):
    """Off / On / Auto run mode (register 65485)."""

    _attr_translation_key = "pump_mode"
    _attr_options = ["Off", "On", "Auto"]

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_mode"

    @property
    def current_option(self) -> str | None:
        option = pump_mode_str(self.reg(REG_PUMP_MODE))
        return option if option in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        value = STR_TO_MODE.get(option)
        if value is None:
            return
        await self.coordinator.async_write_register(REG_PUMP_MODE, value)


class FilterPumpModeSelect(DontekEntity, SelectEntity):
    """Filter Pump (Socket 1) Off / On / Auto (register 65336)."""

    _attr_translation_key = "filter_pump_mode"
    _attr_options = ["Off", "On", "Auto"]

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_filter_pump_mode"

    @property
    def current_option(self) -> str | None:
        return FP_MODE_TO_STR.get(self.reg(REG_FILTER_PUMP_MODE))

    async def async_select_option(self, option: str) -> None:
        value = FP_STR_TO_MODE.get(option)
        if value is None:
            return
        await self.coordinator.async_write_register(REG_FILTER_PUMP_MODE, value)


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


class SocketModeSelect(DontekEntity, SelectEntity):
    """Off / On / Auto for sockets 2-8 (registers 65337-65343).

    Named after the socket's name in the app, or its appliance type if it has
    no name, and follows renames and type changes without a reload. A socket
    set to Always On shows On but can't be switched, as in the app; one set to
    None is unavailable.
    """

    _attr_options = ["Off", "On", "Auto"]

    def __init__(self, coordinator: DontekCoordinator, socket: int) -> None:
        super().__init__(coordinator)
        self._socket = socket
        self._reg = socket_mode_reg(socket)
        self._attr_unique_id = f"{coordinator.mac}_socket{socket}_mode"
        stype = (coordinator.data or {}).get(socket_type_reg(socket))
        self._attr_entity_registry_enabled_default = stype != SOCKET_TYPE_NONE

    @property
    def _type(self) -> int | None:
        return self.reg(socket_type_reg(self._socket))

    @property
    def name(self) -> str:
        return socket_label(self.coordinator.data or {}, self._socket)

    @property
    def available(self) -> bool:
        return super().available and self._type not in (None, SOCKET_TYPE_NONE)

    @property
    def current_option(self) -> str | None:
        return FP_MODE_TO_STR.get(self.reg(self._reg))

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        return {
            "socket": self._socket,
            "appliance_type": socket_type_str(self._type),
            "appliance_name": socket_name(self.coordinator.data or {}, self._socket) or None,
        }

    async def async_select_option(self, option: str) -> None:
        if not socket_controllable(self._type):
            raise HomeAssistantError(
                f"Socket {self._socket} is set to {socket_type_str(self._type)}; "
                "change its type to switch it"
            )
        value = FP_STR_TO_MODE.get(option)
        if value is None:
            return
        await self.coordinator.async_write_register(self._reg, value)


class SocketTypeSelect(DontekEntity, SelectEntity):
    """Appliance type of a socket, as set in the app's Appliance Setup.

    Registers 65323-65330, index into SOCKET_TYPES. The controller turns the
    socket Off when its type changes, like the app does.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(SOCKET_TYPES)

    def __init__(self, coordinator: DontekCoordinator, socket: int) -> None:
        super().__init__(coordinator)
        self._socket = socket
        self._reg = socket_type_reg(socket)
        self._attr_unique_id = f"{coordinator.mac}_socket{socket}_type"

    @property
    def name(self) -> str:
        label = socket_name(self.coordinator.data or {}, self._socket)
        return f"Socket {self._socket} {label} type" if label else f"Socket {self._socket} type"

    @property
    def current_option(self) -> str | None:
        option = socket_type_str(self.reg(self._reg))
        return option if option in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        if option not in SOCKET_TYPES:
            return
        await self.coordinator.async_write_register(self._reg, SOCKET_TYPES.index(option))


class PoolSpaModeSelect(DontekEntity, SelectEntity):
    """Pool / Spa mode (register 65313: 0 = Pool, 1 = Spa).

    Enabled by default only on an Aquatek with Spa Enabled turned on in the
    app's Spa Setup. Otherwise created disabled: Oasis units without a pool-spa
    valve report the register too, and switching it moves a physical actuator
    and starts the pump.
    """

    _attr_translation_key = "pool_spa_mode"
    _attr_options = ["Pool", "Spa"]

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pool_spa_mode"
        regs = coordinator.data or {}
        self._attr_entity_registry_enabled_default = (
            not is_oasis(regs) and regs.get(REG_SPA_ENABLED) == 1
        )

    @property
    def current_option(self) -> str | None:
        return POOL_SPA_TO_STR.get(self.reg(REG_POOL_SPA_MODE))

    async def async_select_option(self, option: str) -> None:
        value = POOL_SPA_STR_TO_MODE.get(option)
        if value is None:
            return
        await self.coordinator.async_write_register(REG_POOL_SPA_MODE, value)


class LightColourSelect(DontekEntity, SelectEntity):
    """Colour of the light on one socket (register 65348 + socket).

    Created for each socket set to Pool Light or Spa Light, at setup or on the
    first poll after a socket becomes one, so moving a light to another socket
    needs no restart. If the socket stops being a light the select is
    unavailable. Only picks the colour; the light's on/off is that socket's
    mode select (#22).

    The register's high byte is the light type from the app's Light Setup, and
    each type has its own colour list. Mapped: type 3 (Aquaquip Instatouch,
    13 colours) and type 6 (SPA Electric Multi Plus, 11 colours). Any other
    type gets generic names (Colour 1, Colour 2, ...) for the same indexes,
    and the light_type / colours_mapped attributes show which it is. With no
    light type set the select is unavailable.
    """

    def __init__(self, coordinator: DontekCoordinator, socket: int) -> None:
        super().__init__(coordinator)
        self._socket = socket
        self._reg = light_colour_reg(socket)
        # Socket 1 keeps the unique id the single colour select had before.
        suffix = "light_colour" if socket == 1 else f"socket{socket}_light_colour"
        self._attr_unique_id = f"{coordinator.mac}_{suffix}"
        regs = coordinator.data or {}
        self._attr_entity_registry_enabled_default = light_colours(regs.get(self._reg)) is not None

    @property
    def options(self) -> list[str]:
        colours = light_colours(self.reg(self._reg))
        return list(colours) if colours else []

    @property
    def name(self) -> str:
        spa = self.reg(socket_type_reg(self._socket)) == 6
        return "Spa light colour" if spa else "Pool light colour"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.reg(socket_type_reg(self._socket)) in SOCKET_TYPES_LIGHT
            and light_colours(self.reg(self._reg)) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, int | bool | None]:
        value = self.reg(self._reg)
        return {
            "socket": self._socket,
            "light_type": light_type(value),
            "colours_mapped": light_type_mapped(value),
        }

    @property
    def current_option(self) -> str | None:
        return light_colour_str(self.reg(self._reg))

    async def async_select_option(self, option: str) -> None:
        current = self.reg(self._reg)
        colours = light_colours(current)
        if self.reg(socket_type_reg(self._socket)) not in SOCKET_TYPES_LIGHT:
            raise HomeAssistantError(
                f"Socket {self._socket} isn't set to Pool Light or Spa Light any more"
            )
        if colours is None:
            raise HomeAssistantError(
                f"No light type is set for socket {self._socket}; pick one in the app's "
                "Light Setup"
            )
        if option not in colours:
            return
        await self.coordinator.async_write_register(
            self._reg, light_colour_value(current, option)
        )
