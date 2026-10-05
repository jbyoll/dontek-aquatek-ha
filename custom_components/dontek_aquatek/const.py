"""Constants for the Dontek Aquatek integration."""
from __future__ import annotations

DOMAIN = "dontek_aquatek"

CONF_SERIAL = "serial"
CONF_MAC = "mac"
CONF_NAME = "name"

DEFAULT_NAME = "Pool Pump"
DEFAULT_SCAN_INTERVAL = 30  # seconds between full register reads

# --- Register map (reverse engineered; all values are unsigned 16-bit) ---
# Water temperature is fixed-point Q8.8: degrees C = raw / 256.
REG_WATER_TEMP = 57545

# Pump run mode.
REG_PUMP_MODE = 65485
MODE_OFF = 0
MODE_ON = 1025
MODE_AUTO = 65535
MODE_TO_STR = {MODE_OFF: "Off", MODE_ON: "On", MODE_AUTO: "Auto"}
STR_TO_MODE = {v: k for k, v in MODE_TO_STR.items()}

# Filter Pump = the Socket 1 appliance relay (a separate pump the controller
# switches on/off/auto), distinct from the Hayward variable-speed pump above.
# Mapped live 2026-10-04 by watching the app's writes. Simple 0/1/2 encoding.
REG_FILTER_PUMP_MODE = 65336
FP_MODE_TO_STR = {0: "Off", 1: "On", 2: "Auto"}
FP_STR_TO_MODE = {v: k for k, v in FP_MODE_TO_STR.items()}

# Pump speed selector. Register is zero-based; displayed speed = value + 1 (4 speeds).
REG_PUMP_SPEED = 65463
SPEED_COUNT = 4

# NOTE: the per-speed RPM setpoint registers are not mapped yet. (65319-65322,
# previously listed here as REG_SPEED_RPM, are the Filter Time 1/2 from/to times.)

# Per-speed power as a percentage (what the app's Pump Setup screen edits).
REG_SPEED_PCT = {1: 65478, 2: 65479, 3: 65480, 4: 65481}

# Live run-state word: high byte = state, low byte = running speed index (0-3).
REG_RUN_STATE = 92

# Filter Time 1 schedule (in Auto mode the pump follows this, not the set speed).
# Times are packed as hour * 256 + minute.
REG_FT1_ENABLE = 65318
REG_FT1_FROM = 65319
REG_FT1_TO = 65320
REG_FT1_SPEED = 65473  # 0-based (0-3 -> Speed 1-4)


def reg_to_hm(value: int) -> tuple[int, int]:
    """Decode a packed time register into (hour, minute)."""
    hour = (value >> 8) & 0xFF
    minute = value & 0xFF
    if hour > 23 or minute > 59:
        return 0, 0
    return hour, minute


def hm_to_reg(hour: int, minute: int) -> int:
    """Encode (hour, minute) into a packed time register value."""
    return (int(hour) << 8) | (int(minute) & 0xFF)
RUN_STATE = {
    0: "Off",
    1: "Off",
    2: "Powering up",
    3: "Powering up",
    4: "Powering up",
    5: "Priming",
    6: "Setting speed",
    7: "Setting speed",
    8: "Setting speed",
    9: "Switching on",
    10: "Switching on",
    11: "Switching on",
    12: "Running",
}
RUN_STATE_RUNNING = 12

# --- All four Filter Time schedules (mapped live 2026-10-04 by diff) ---
# Enable is a BITMASK in REG_FT_ENABLE_MASK: bit (n-1) set => Filter Time n on.
# Observed: reg 65318 = 1 (FT1 only) ... 15 (all four enabled).
REG_FT_ENABLE_MASK = 65318
FILTER_TIME_COUNT = 4
# from/to are packed hour*256+minute; speed is 0-based (0-3 -> Speed 1-4).
FILTER_TIMES = {
    1: {"from": 65319, "to": 65320, "speed": 65473},
    2: {"from": 65321, "to": 65322, "speed": 65474},
    3: {"from": 65469, "to": 65470, "speed": 65475},
    4: {"from": 65471, "to": 65472, "speed": 65476},
}

# Run Once (one-shot): write start = now, end = now + duration (both packed
# hour*256+minute, using the controller's own clock), then enable = 1. The two
# time registers reject invalid values but accept valid times. 0xFF00 = off.
REG_RUNONCE_ENABLE = 57630
REG_RUNONCE_START = 57650
REG_RUNONCE_END = 57670
RUNONCE_OFF = 0xFF00  # 65280

# Controller real-time clock (used to anchor the Run Once window to "now").
REG_CLOCK_HOUR = 65299
REG_CLOCK_MIN = 65300

# Default Run Once duration if the duration number hasn't been set.
RUNONCE_DEFAULT_MIN = 15

# --- Heater (mapped live 2026-10-06 by watching the app's writes) ---
# Heater socket on/off - the app offers only On/Off for the heater (no Auto).
REG_HEATER_ON = 65348
# Setpoint in half-degrees: value = degrees C * 2 (76 = 38.0 C, 80 = 40.0 C).
REG_HEATER_SETPOINT = 65447
HEATER_MIN_TEMP = 10.0
HEATER_MAX_TEMP = 40.0
# "Run til heated" setting (0/1): heater stops once the setpoint is reached
# instead of staying in heat mode. Writing it doesn't start/stop the heater.
REG_HEATER_RUN_TIL_HEATED = 65500
# Live heater status: 1 while the controller is calling for heat.
REG_HEATER_ACTIVE = 172

# Water Feature socket on/off (0/1). Often drives a valve/jets (e.g. spa jets).
REG_WATER_FEATURE = 65345
