"""Constants for the Dontek Aquatek integration."""
from __future__ import annotations

DOMAIN = "dontek_aquatek"

CONF_SERIAL = "serial"
CONF_MAC = "mac"
CONF_NAME = "name"

DEFAULT_NAME = "Pool Pump"
DEFAULT_SCAN_INTERVAL = 30  # seconds between full register reads

# --- Register map (reverse engineered; all values are unsigned 16-bit) ---
# Water temperature in half-degrees (56 = 28.0 C); registers 55 and 57 mirror
# it. This is what the app shows on Aquatek (fw 1.17B1, checked 2026-10-18)
# and Oasis units.
REG_WATER_TEMP_HALF = 79
# Older mapping, fixed-point Q8.8 (degrees C = raw / 256). Reads 0 on the
# units above; kept as a fallback for controllers without register 79.
REG_WATER_TEMP = 57545


def water_temp_c(regs: dict[int, int]) -> float | None:
    """Water temperature in C from whichever register this controller fills."""
    half = regs.get(REG_WATER_TEMP_HALF)
    if half:
        return half / 2
    raw = regs.get(REG_WATER_TEMP)
    if raw:
        return round(raw / 256, 1)
    if half is None and raw is None:
        return None
    return 0.0

# Pump run mode.
REG_PUMP_MODE = 65485
MODE_OFF = 0
MODE_ON = 1025
MODE_AUTO = 65535
MODE_TO_STR = {MODE_OFF: "Off", MODE_ON: "On", MODE_AUTO: "Auto"}
STR_TO_MODE = {v: k for k, v in MODE_TO_STR.items()}


def pump_mode_str(value: int | None) -> str | None:
    """Decode the pump mode register, tolerating other pump types.

    Aquatek + Hayward VSP reports 0 / 1025 (0x0401) / 65535. Other setups have
    been seen reporting 257 (0x0101) for On, so fall back to the low byte:
    0 = Off, 1 = On, 0xFFFF = Auto.
    """
    if value is None:
        return None
    if value in MODE_TO_STR:
        return MODE_TO_STR[value]
    low = value & 0xFF
    if low == 1:
        return "On"
    if low == 0:
        return "Off"
    return f"Unknown ({value})"


# Filter Pump = the Socket 1 appliance relay (a separate pump the controller
# switches on/off/auto), distinct from the Hayward variable-speed pump above.
# Mapped live 2026-10-04 by watching the app's writes. Simple 0/1/2 encoding.
REG_FILTER_PUMP_MODE = 65336
FP_MODE_TO_STR = {0: "Off", 1: "On", 2: "Auto"}
FP_STR_TO_MODE = {v: k for k, v in FP_MODE_TO_STR.items()}

# --- Sockets (mapped live 2026-10-18 on an Aquatek, fw 1.17B1 + Expansion 1) ---
# Sockets 1-2 are on the main unit, 3-5 on Expansion 1. Each socket has a type
# (what the app's Appliance Setup assigns to it), an Off/On/Auto mode (same
# 0/1/2 encoding as REG_FILTER_PUMP_MODE, which is socket 1's mode) and an
# optional 16-character name the owner can set in the app. Changing a socket's
# type resets its mode to Off (seen live).
SOCKET_COUNT = 5
REG_SOCKET_TYPE_BASE = 65323  # socket n type = 65323 + (n - 1)
REG_SOCKET_MODE_BASE = 65336  # socket n mode = 65336 + (n - 1)
REG_SOCKET_NAME_BASE = 57344  # socket n name = 8 registers from 57344 + 8 * (n - 1)
SOCKET_NAME_REGS = 8
SOCKET_NAME_MAX_LEN = SOCKET_NAME_REGS * 2  # app limit: 16 characters
# Appliance types, in the app's order (index = register value).
SOCKET_TYPES = (
    "None",
    "Sanitiser",
    "Filter Pump",
    "Cleaning Pump",
    "Blower",
    "Pool Light",
    "Spa Light",
    "Garden Light",
    "Water Feature",
    "Solar",
    "Other",
    "Always On",
    "Jet Pump",
    "Heating Pump (ind.)",
    "UV Sanitiser",
)
SOCKET_TYPE_NONE = 0
SOCKET_TYPE_ALWAYS_ON = 11


def socket_type_reg(socket: int) -> int:
    return REG_SOCKET_TYPE_BASE + socket - 1


def socket_mode_reg(socket: int) -> int:
    return REG_SOCKET_MODE_BASE + socket - 1


def socket_type_str(value: int | None) -> str | None:
    if value is None:
        return None
    if 0 <= value < len(SOCKET_TYPES):
        return SOCKET_TYPES[value]
    return f"Unknown ({value})"


def _ascii(regs: dict[int, int], start: int, count: int) -> str:
    chars = []
    for reg in range(start, start + count):
        val = regs.get(reg)
        if val is None:
            break
        for b in (val >> 8, val & 0xFF):
            if 32 <= b < 127:
                chars.append(chr(b))
    return "".join(chars).strip()


def socket_name_reg(socket: int) -> int:
    return REG_SOCKET_NAME_BASE + SOCKET_NAME_REGS * (socket - 1)


def socket_name(regs: dict[int, int], socket: int) -> str:
    """Name the owner gave the socket in the app ("" if none)."""
    return _ascii(regs, socket_name_reg(socket), SOCKET_NAME_REGS)


def encode_name(name: str) -> list[int]:
    """Pack a name into the 8 name registers, 2 characters each, zero padded.

    The app writes all 8 registers in one message; an empty name is 8 zeros.
    """
    data = name.encode("ascii")[: SOCKET_NAME_MAX_LEN].ljust(SOCKET_NAME_MAX_LEN, b"\0")
    return [(data[i] << 8) | data[i + 1] for i in range(0, SOCKET_NAME_MAX_LEN, 2)]


def socket_controllable(type_value: int | None) -> bool:
    """True for appliance types the app gives an Off / On / Auto control."""
    return type_value is not None and type_value not in (
        SOCKET_TYPE_NONE,
        SOCKET_TYPE_ALWAYS_ON,
    )


def socket_label(regs: dict[int, int], socket: int) -> str:
    """"Socket 3 Jets": the socket's name, or its type if it has no name."""
    label = socket_name(regs, socket) or socket_type_str(regs.get(socket_type_reg(socket)))
    return f"Socket {socket} {label}" if label else f"Socket {socket}"


# Valve 1-4 type (0 = None). Valve modes aren't mapped yet: no test unit has a
# valve assigned.
REG_VALVE_TYPE_BASE = 65328
VALVE_COUNT = 4

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
# Heater socket. The Aquatek app offers only On/Off (0/1). Oasis units use
# 0/1/2 = Off/On/Auto (the Oasis app shows "Heat Pump: Auto"); the climate
# entity only offers Auto when the controller reports as Oasis.
REG_HEATER_ON = 65348
HEATER_MODE_AUTO = 2
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

# --- Oasis Smart units (mapped live 2026-10-18 against the Oasis app) ---
# Controller name as ASCII, two characters per register ("OASIS" on Oasis
# Smart units). Used to tell Oasis controllers apart from Aquatek ones.
REG_NAME_START = 65488
REG_NAME_COUNT = 8
# Pool / Spa mode: 0 = Pool, 1 = Spa (registers 168/169 mirror it on Oasis).
# Same register on Aquatek (confirmed 2026-10-18); there the app only offers
# Pool/Spa once Spa Setup > Spa Enabled (REG_SPA_ENABLED) is on, and switching
# to Spa starts the pump at the spa speed.
REG_POOL_SPA_MODE = 65313
REG_SPA_ENABLED = 65482  # 0 / 1
POOL_SPA_TO_STR = {0: "Pool", 1: "Spa"}
POOL_SPA_STR_TO_MODE = {v: k for k, v in POOL_SPA_TO_STR.items()}
# Roof / solar collector temperature in half-degrees (113 = 56.5 C); registers
# 54 and 56 mirror it. Reads 0 on units without a roof sensor.
REG_ROOF_TEMP_HALF = 80
# Solar pump running flag (sits next to 160 filter / 172 heater).
REG_SOLAR_PUMP_ACTIVE = 162


def decode_name(regs: dict[int, int]) -> str:
    """Controller name from the ASCII name registers ("" if not present)."""
    return _ascii(regs, REG_NAME_START, REG_NAME_COUNT)


def is_oasis(regs: dict[int, int]) -> bool:
    """True when the controller reports as an Oasis Smart unit."""
    return decode_name(regs).upper().startswith("OASIS")
