# Dontek Aquatek Pool Controller — Home Assistant integration

Local-cloud control of **Dontek** pool controllers (sold as **Aquatek**, **Theralux Pool+ Manager**,
**Waterco Pooltek**, **Aquamate X** and similar) from Home Assistant.

It talks to Dontek's AWS IoT cloud the same way the official app does, so it works from anywhere
without any extra hardware or a local gateway.

> ⚠️ **Status: early / community reverse-engineered.** Built for a single-pump (variable-speed pump)
> setup. It does **not** use any official Dontek API and may break if Dontek changes their backend.
> Not affiliated with or endorsed by Dontek Electronics.

## Features

- **Water temperature** sensor
- **Pump status** sensor (Off / On / Auto)
- **Pump speed** sensor (1–4)
- **Pump mode** select — Off / On / Auto
- **Pump speed set** select — 1 / 2 / 3 / 4

## Installation (HACS)

1. HACS → ⋮ → *Custom repositories* → add this repo, category **Integration**.
2. Install **Dontek Aquatek Pool Controller**, then restart Home Assistant.
3. *Settings → Devices & Services → Add Integration →* **Dontek Aquatek**.
4. Enter the **serial number** printed on the controller label (the long number under the QR code),
   e.g. `56559560543361145`. You can also enter the 12-character MAC directly.

(Manual install: copy `custom_components/dontek_aquatek` into your HA `config/custom_components/`.)

## How it works

- The controller has **no local API** — on your LAN it only serves a Wi-Fi setup page. All control
  is via Dontek's AWS cloud.
- Auth is an **anonymous AWS Cognito identity pool** (guest credentials — no username/password).
- Transport is **AWS IoT MQTT over WebSockets** (SigV4-signed). This integration uses Home
  Assistant's bundled `paho-mqtt` and signs the connection itself, so it has **no extra Python
  dependencies** (no `boto3` / `awscrt`).
- The controller speaks **Modbus-over-MQTT**: a JSON message
  `{"messageId":"read"|"write","modbusReg":R,"modbusVal":[...]}` on
  `dontek<mac>/cmd/psw`, with the controller replying on `dontek<mac>/status/psw`.

### Register map used

| What | Register | Encoding |
|---|---|---|
| Water temperature | 57545 | °C = raw / 256 |
| Pump mode | 65485 | 0 = Off, 1025 = On, 65535 = Auto |
| Pump speed select | 65463 | 0–3 → Speed 1–4 (display = value + 1) |
| Speed 1–4 RPM setpoints | 65319–65322 | RPM |

## Security note

Dontek's guest cloud policy is broad: any client that knows a controller's MAC can read and write
its registers, and the MAC is derived from the serial printed on the label. Keep your serial/QR
private. This integration only talks to the controller you configure.

## Roadmap / help wanted

- Map the remaining registers (flow, power/RPM readback, schedules, chlorinator/heater on units that
  have them).
- Support multiple appliances / expansion modules.
- Optional `number` entities for the per-speed RPM setpoints.

PRs and register captures from other Dontek models welcome.

## License

MIT
