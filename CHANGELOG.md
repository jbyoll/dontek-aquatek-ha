# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/jbyoll/dontek-aquatek-ha/releases/tag/v0.1.0
