"""Switch entities for Dontek Aquatek (Filter Time enables, valves, heater extras)."""
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
    VALVE_COUNT,
    VALVE_TYPES_MANUAL,
    valve_mode_reg,
    valve_switchable,
    valve_type_reg,
    valve_type_str,
    water_feature_valve,
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
    # optional features: created disabled (see RegisterSwitch), because units
    # without the hardware report these registers too
    regs = coordinator.data or {}
    # a setting, not a control: heater stops once at temperature
    if REG_HEATER_RUN_TIL_HEATED in regs:
        entities.append(
            RegisterSwitch(
                coordinator, REG_HEATER_RUN_TIL_HEATED, "run_til_heated", EntityCategory.CONFIG
            )
        )
    # One switch per valve that has a function other than Pool/Spa (#23).
    switchable = [
        valve
        for valve in range(1, VALVE_COUNT + 1)
        if valve_switchable(regs.get(valve_type_reg(valve))) and valve_mode_reg(valve) in regs
    ]
    # The old "Water feature" entity (register 65345 = valve 2) carries over to
    # the valve typed Water Feature, else to valve 2 if it has a switch, so an
    # existing entity id keeps working and no register gets two switches.
    legacy_valve = water_feature_valve(regs)
    if legacy_valve not in switchable:
        legacy_valve = 2 if 2 in switchable else None
    for valve in switchable:
        entities.append(ValveSwitch(coordinator, valve, legacy=valve == legacy_valve))
    if legacy_valve is None and REG_WATER_FEATURE in regs:
        # no valve switch to carry it: keep the pre-0.14 switch on 65345 as it was
        entities.append(RegisterSwitch(coordinator, REG_WATER_FEATURE, "water_feature"))
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
        await self.coordinator.async_update_bits(REG_FT_ENABLE_MASK, self._bit, 0)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_update_bits(REG_FT_ENABLE_MASK, 0, self._bit)


class RegisterSwitch(DontekEntity, SwitchEntity):
    """A plain 0/1 register (Run til heated 65500, Water Feature 65345)."""

    # optional hardware: off until the owner enables it
    _attr_entity_registry_enabled_default = False

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


class ValveSwitch(DontekEntity, SwitchEntity):
    """On/off for a valve with a function assigned in the app (65344 + (n - 1)).

    Named like the valve's binary sensor ("Valve 3 Water Feature"). The valve
    typed Water Feature keeps the unique id of the old "Water feature" switch,
    so existing entity ids and automations carry over. Switches for Solar,
    In Floor and Heating valves are created disabled, since the controller
    moves those itself.
    """

    def __init__(self, coordinator: DontekCoordinator, valve: int, legacy: bool = False) -> None:
        super().__init__(coordinator)
        self._valve = valve
        self._reg = valve_mode_reg(valve)
        key = "water_feature" if legacy else f"valve{valve}_switch"
        self._attr_unique_id = f"{coordinator.mac}_{key}"
        vtype = (coordinator.data or {}).get(valve_type_reg(valve))
        self._attr_entity_registry_enabled_default = vtype in VALVE_TYPES_MANUAL

    @property
    def _type(self) -> int | None:
        return self.reg(valve_type_reg(self._valve))

    @property
    def name(self) -> str:
        vtype = valve_type_str(self._type)
        return f"Valve {self._valve} {vtype}" if vtype else f"Valve {self._valve}"

    @property
    def available(self) -> bool:
        return super().available and valve_switchable(self._type)

    @property
    def is_on(self) -> bool | None:
        value = self.reg(self._reg)
        return None if value is None else value != 0

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        return {
            "valve": self._valve,
            "valve_type": valve_type_str(self._type),
            "mode_register": self._reg,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(self._reg, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_register(self._reg, 0)
