"""Select entities for Dontek Aquatek (pump, sockets, pool/spa)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    SOCKET_TYPE_ALWAYS_ON,
    SOCKET_TYPE_NONE,
    SPEED_COUNT,
    STR_TO_MODE,
    is_oasis,
    pump_mode_str,
    socket_mode_reg,
    socket_name,
    socket_type_reg,
    socket_type_str,
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
        FilterPumpModeSelect(coordinator),
    ]
    for ft, regs in FILTER_TIMES.items():
        entities.append(FilterTimeSpeedSelect(coordinator, ft, regs["speed"]))
    regs = coordinator.data or {}
    # Socket 1 is the Filter Pump select above. Sockets set to None or Always
    # On have no Off/On/Auto control in the app, so they get no entity.
    for socket in range(2, SOCKET_COUNT + 1):
        stype = regs.get(socket_type_reg(socket))
        if stype is None or stype in (SOCKET_TYPE_NONE, SOCKET_TYPE_ALWAYS_ON):
            continue
        entities.append(SocketModeSelect(coordinator, socket))
    if REG_POOL_SPA_MODE in regs:
        entities.append(PoolSpaModeSelect(coordinator))
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
    """Off / On / Auto for sockets 2-5 (registers 65337-65340).

    Named after the socket's name in the app, or its appliance type if it has
    no name. Reload the integration after changing Appliance Setup in the app.
    """

    _attr_options = ["Off", "On", "Auto"]

    def __init__(self, coordinator: DontekCoordinator, socket: int) -> None:
        super().__init__(coordinator)
        self._socket = socket
        self._reg = socket_mode_reg(socket)
        regs = coordinator.data or {}
        label = socket_name(regs, socket) or socket_type_str(
            regs.get(socket_type_reg(socket))
        )
        self._attr_name = f"Socket {socket} {label}"
        self._attr_unique_id = f"{coordinator.mac}_socket{socket}_mode"

    @property
    def current_option(self) -> str | None:
        return FP_MODE_TO_STR.get(self.reg(self._reg))

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        return {
            "socket": self._socket,
            "appliance_type": socket_type_str(self.reg(socket_type_reg(self._socket))),
        }

    async def async_select_option(self, option: str) -> None:
        value = FP_STR_TO_MODE.get(option)
        if value is None:
            return
        await self.coordinator.async_write_register(self._reg, value)


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
