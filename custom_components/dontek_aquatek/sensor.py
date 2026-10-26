"""Sensors for Dontek Aquatek."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_ORP,
    REG_ORP_SETPOINT,
    REG_PH,
    REG_PH_SETPOINT,
    REG_PUMP_MODE,
    REG_ROOF_TEMP_HALF,
    REG_RUN_STATE,
    RUN_STATE,
    RUN_STATE_RUNNING,
    SPEED_COUNT,
    is_oasis,
    orp_value,
    ph_value,
    pump_mode_str,
    water_temp_c,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[DontekEntity] = [
        WaterTemperatureSensor(coordinator),
        PumpStatusSensor(coordinator),
        PumpActivitySensor(coordinator),
        RunningSpeedSensor(coordinator),
    ]
    regs = coordinator.data or {}
    if is_oasis(regs):
        entities.append(RoofTemperatureSensor(coordinator))
    # chemistry module (#22): enabled by default only when it reports a reading
    if REG_PH in regs:
        entities.append(PhSensor(coordinator))
    if REG_ORP in regs:
        entities.append(OrpSensor(coordinator))
    if REG_PH_SETPOINT in regs:
        entities.append(PhSensor(coordinator, setpoint=True))
    if REG_ORP_SETPOINT in regs:
        entities.append(OrpSensor(coordinator, setpoint=True))
    async_add_entities(entities)


class WaterTemperatureSensor(DontekEntity, SensorEntity):
    """Pool water temperature (register 79 in half-degrees, or 57545 Q8.8)."""

    _attr_translation_key = "water_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_water_temp"

    @property
    def native_value(self) -> float | None:
        return water_temp_c(self.coordinator.data or {})


class PumpStatusSensor(DontekEntity, SensorEntity):
    """Pump run mode as text (Off / On / Auto)."""

    _attr_translation_key = "pump_status"

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_status"

    @property
    def native_value(self) -> str | None:
        return pump_mode_str(self.reg(REG_PUMP_MODE))


class PumpActivitySensor(DontekEntity, SensorEntity):
    """What the pump is doing right now (Running / Priming / Idle / ...)."""

    _attr_translation_key = "pump_activity"

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_pump_activity"

    @property
    def native_value(self) -> str | None:
        word = self.reg(REG_RUN_STATE)
        if word is None:
            return None
        state = (word >> 8) & 0xFF
        return RUN_STATE.get(state, "Idle")


class RunningSpeedSensor(DontekEntity, SensorEntity):
    """The speed the pump is actually running at right now (1-4).

    This reflects the live filter schedule and can differ from the set speed
    while in Auto mode. It is only meaningful while the pump is running.
    """

    _attr_translation_key = "running_speed"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_running_speed"

    @property
    def native_value(self) -> int | None:
        word = self.reg(REG_RUN_STATE)
        if word is None:
            return None
        state = (word >> 8) & 0xFF
        speed = word & 0xFF  # 0-based speed index
        if state != RUN_STATE_RUNNING or speed >= SPEED_COUNT:
            # not running, or no index in the low byte (Oasis reports 0xFF)
            return None
        return speed + 1


class RoofTemperatureSensor(DontekEntity, SensorEntity):
    """Roof / solar collector temperature on Oasis units (register 80, half-degrees).

    Created disabled: Oasis units without a roof sensor report 0 here.
    """

    _attr_translation_key = "roof_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: DontekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_roof_temp"

    @property
    def native_value(self) -> float | None:
        raw = self.reg(REG_ROOF_TEMP_HALF)
        if not raw:
            return None  # 0 = no roof sensor fitted
        return raw / 2


class PhSensor(DontekEntity, SensorEntity):
    """Pool pH from a chemistry module (register 173, pH x 10), or its set point
    (register 65503, same encoding) when setpoint=True.

    Enabled by default only if the controller reports a plausible value at
    setup; unavailable while it doesn't (no chemistry module). The set point
    is read-only on purpose: changing it changes chemical dosing (#22).
    """

    _attr_device_class = SensorDeviceClass.PH
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: DontekCoordinator, setpoint: bool = False) -> None:
        super().__init__(coordinator)
        self._reg = REG_PH_SETPOINT if setpoint else REG_PH
        self._attr_translation_key = "ph_setpoint" if setpoint else "ph"
        self._attr_unique_id = f"{coordinator.mac}_{self._attr_translation_key}"
        if not setpoint:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = (
            ph_value((coordinator.data or {}).get(self._reg)) is not None
        )

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        return ph_value(self.reg(self._reg))


class OrpSensor(DontekEntity, SensorEntity):
    """Pool ORP from a chemistry module (register 174, mV / 10), or its set
    point (register 65502, same encoding) when setpoint=True.

    Enabled by default only if the controller reports a plausible value at
    setup; unavailable while it doesn't (no chemistry module). The set point
    is read-only on purpose: changing it changes chemical dosing (#22).
    """

    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_icon = "mdi:flask-outline"

    def __init__(self, coordinator: DontekCoordinator, setpoint: bool = False) -> None:
        super().__init__(coordinator)
        self._reg = REG_ORP_SETPOINT if setpoint else REG_ORP
        self._attr_translation_key = "orp_setpoint" if setpoint else "orp"
        self._attr_unique_id = f"{coordinator.mac}_{self._attr_translation_key}"
        if not setpoint:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = (
            orp_value((coordinator.data or {}).get(self._reg)) is not None
        )

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> int | None:
        return orp_value(self.reg(self._reg))
