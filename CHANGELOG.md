# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
