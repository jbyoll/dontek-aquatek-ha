"""Climate entity for Dontek Aquatek (pool heater)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    HEATER_MAX_TEMP,
    HEATER_MIN_TEMP,
    REG_HEATER_ACTIVE,
    REG_HEATER_ON,
    REG_HEATER_SETPOINT,
    REG_WATER_TEMP,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    # A controller with no heater has been seen reporting the heater registers, so
    # their presence does not prove a heater is fitted: the entity is
    # created disabled and the owner enables it (see HeaterClimate).
    regs = coordinator.data or {}
    if REG_HEATER_ON in regs and REG_HEATER_SETPOINT in regs:
        async_add_entities([HeaterClimate(coordinator)])


class HeaterClimate(DontekEntity, ClimateEntity):
    """Heater on/off (65348) with setpoint in half-degrees (65447)."""

    _attr_translation_key = "heater"
    # off until the owner enables it: units without a heater report the same
    # registers, and switching the heater socket also changes the pump speed
    _attr_entity_registry_enabled_default = False
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    # TURN_ON/TURN_OFF only exist from HA 2024.2; hacs.json still allows 2024.1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | getattr(ClimateEntityFeature, "TURN_ON", 0)
        | getattr(ClimateEntityFeature, "TURN_OFF", 0)
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = HEATER_MIN_TEMP
    _attr_max_temp = HEATER_MAX_TEMP
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_heater"

    @property
    def hvac_mode(self) -> HVACMode | None:
        on = self.reg(REG_HEATER_ON)
        if on is None:
            return None
        return HVACMode.HEAT if on else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        active = self.reg(REG_HEATER_ACTIVE)
        if active is None:
            return None
        # 1 = calling for heat. A unit with no heater has been seen reporting 2 here.
        return HVACAction.HEATING if active == 1 else HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        raw = self.reg(REG_WATER_TEMP)
        if raw is None:
            return None
        return round(raw / 256, 1)

    @property
    def target_temperature(self) -> float | None:
        raw = self.reg(REG_HEATER_SETPOINT)
        if raw is None:
            return None
        return raw / 2

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        # clamp before encoding so a bad value can never reach the heater
        temp = min(max(float(temp), HEATER_MIN_TEMP), HEATER_MAX_TEMP)
        await self.coordinator.async_write_register(
            REG_HEATER_SETPOINT, int(round(temp * 2))
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self._attr_hvac_modes:
            return
        await self.coordinator.async_write_register(
            REG_HEATER_ON, 1 if hvac_mode == HVACMode.HEAT else 0
        )

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
