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

# Pump speed selector. Register is zero-based; displayed speed = value + 1 (4 speeds).
REG_PUMP_SPEED = 65463
SPEED_COUNT = 4

# RPM setpoints for speeds 1..4.
REG_SPEED_RPM = {1: 65319, 2: 65320, 3: 65321, 4: 65322}

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
