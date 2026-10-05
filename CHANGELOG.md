# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-10-06

### Added
- **Heater** support (mapped live from the app's writes; only created on units that
  report the heater registers). Tested with a Waterco Electroheat MKV 9 kW heat pump on a
  Pooltek controller:
  - `climate` **Heater** — Off / Heat (register 65348; the app has no heater Auto),
    target temperature in 0.5 °C steps (65447, encoded as °C × 2, clamped to 10–40 °C),
    current temperature from the water sensor, heating/idle from 172.
  - `switch` **Run til heated** (65500, config) — setting that makes the heater stop once
    the setpoint is reached rather than staying in heat mode.
- `switch` **Water feature** (Socket, register 65345) — often drives a valve or jets.
- `tools/dontek_capture.py` — register capture tool for contributors: watches the app's
  writes, diffs full dumps around typed markers, writes a raw `.jsonl` log plus a
  Markdown summary ready to attach to an issue.

### Fixed
- Removed `REG_SPEED_RPM`, which wrongly pointed at the Filter Time 1/2 start/end
  registers (65319–65322).

## [0.6.0] - 2026-10-05

### Added
- **Run Once** — a one-shot "run the pump now for N minutes":
  - `button` **Run once** — starts the run immediately.
  - `number` **Run once minutes** (config, 1–180, default 15) — how long it runs.
  - Works by anchoring the run window to the controller's own clock (writes start = now,
    end = now + minutes to registers 57650/57670, then enable = 57630).

## [0.5.2] - 2026-10-05

### Fixed
- **Polling could wedge permanently after a dropped connection** (the real cause behind
  the stale data 0.5.1 tried to address). When the websocket dropped, the next poll tore
  the old client down with paho's `loop_stop()`, which *joins* the network thread — and if
  that thread was blocked on a dead socket, the join never returned, hanging that poll and
  every poll after it (values frozen, but the entity still showed "available"). The old
  client is now torn down on a throwaway daemon thread so reconnects never block, and the
  coordinator poll has a hard 50 s ceiling as a backstop.

## [0.5.1] - 2026-10-05

### Fixed
- **Stale data after a dropped connection.** AWS IoT can close the websocket without a
  clean disconnect, leaving the `connected` flag `True`; the coordinator then published
  reads into a dead socket and, because the register cache was already non-empty, served
  the last values indefinitely while appearing "available". The coordinator now tracks a
  last-reply timestamp and requires a **fresh** status reply every poll, forcing a
  reconnect (with newly signed credentials) and one retry if none arrives — and marking
  the device unavailable rather than showing stale readings if it still can't reach the cloud.

## [0.5.0] - 2026-10-04

### Added
- **Filter pump mode** — `select` for the Socket 1 appliance relay (Off / On / Auto,
  register 65336). This is the controller's second pump output, separate from the
  Hayward variable-speed pump. Mapped live from the app's own writes.

### Notes
- Confirmed (by driving the vendor app end-to-end) that on this controller the only
  switchable outputs are the two pumps; the other sockets are "Always On" and no
  lights / heating / solar / spa / valves are wired, so there is nothing further to map
  unless the hardware configuration changes.

## [0.4.0] - 2026-10-04

### Added
- **Filter Times 2, 3 and 4** — full read/write for all four schedules the pump can
  follow in Auto mode (previously only Filter Time 1 was exposed):
  - `switch` **Filter N enabled** (N = 1–4)
  - `time` **Filter N start** / **Filter N end**
  - `select` **Filter N speed**
  - Registers: FT1 65319/65320/65473, FT2 65321/65322/65474,
    FT3 65469/65470/65475, FT4 65471/65472/65476 (mapped by live capture).

### Fixed
- **Filter Time enable is a bitmask.** Register 65318 holds one bit per schedule
  (bit 0 = FT1 … bit 3 = FT4), not a per-schedule boolean. Enabling/disabling a
  Filter Time now flips only its bit via read-modify-write, so toggling one schedule
  no longer wipes the others. (Previously writing 0/1 to 65318 could clear FT2–4.)

### Notes
- Run Once (one-shot "run for N minutes") was also mapped (enable 57630, absolute
  start/end 57650/57670) but is not yet exposed as entities.

## [0.3.1] - 2026-10-04

### Fixed
- Pump activity now shows **Off** when the pump is stopped (controller state code 0/1)
  instead of the incorrect "Idle".

## [0.3.0] - 2026-10-04

### Added
- **Filter Time 1 schedule controls** — the schedule the pump follows in Auto mode:
  - `switch` **Filter 1 enabled** (register 65318)
  - `time` **Filter 1 start** / **Filter 1 end** (registers 65319 / 65320)
  - `select` **Filter 1 speed** (register 65473)

## [0.2.0] - 2026-10-04

### Added
- **Pump activity** sensor — live state (Running / Priming / Idle …) from register 92.
- **Running speed** sensor — the speed the pump is actually running at (1–4), which can differ
  from the set speed while in Auto mode.
- **Speed 1–4 power** number entities — tune each speed's power % (registers 65478–65481).

### Changed
- "Pump speed set" select renamed to **Pump speed**; "Pump status" renamed to **Pump mode
  status**. The old **Pump speed** sensor (which showed the *set* speed, duplicating the
  select) is replaced by the new **Running speed** sensor.

## [0.1.0] - 2026-10-04

Initial release.

### Added
- Cloud connection to Dontek controllers via anonymous AWS Cognito + AWS IoT MQTT over
  WebSockets (SigV4-signed), using only Home Assistant's bundled `paho-mqtt`.
- Config flow that takes the controller serial number (or MAC) and verifies connectivity.
- Entities:
  - Water temperature sensor (register 57545 ÷ 256).
  - Pump status sensor (Off / On / Auto).
  - Pump speed sensor (1–4).
  - Pump mode select (Off / On / Auto).
  - Pump speed selector (1–4).

[0.3.1]: https://github.com/jbyoll/dontek-aquatek-ha/releases/tag/v0.3.1
[0.3.0]: https://github.com/jbyoll/dontek-aquatek-ha/releases/tag/v0.3.0
[0.2.0]: https://github.com/jbyoll/dontek-aquatek-ha/releases/tag/v0.2.0
[0.1.0]: https://github.com/jbyoll/dontek-aquatek-ha/releases/tag/v0.1.0
