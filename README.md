<p align="center">
  <img src="assets/banner.png" alt="Dontek Aquatek for Home Assistant" width="100%">
</p>

<h1 align="center">Dontek Aquatek — <i>Unofficial</i> Home Assistant integration</h1>

<p align="center">
  Control your <b>Dontek</b> pool controller from Home Assistant — water temperature,
  pump mode and variable pump speed — over the same cloud the official app uses.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-unofficial-orange.svg?style=for-the-badge" alt="Unofficial">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge" alt="HACS Custom"></a>
  <a href="https://github.com/jbyoll/dontek-aquatek-ha/releases"><img src="https://img.shields.io/github/v/release/jbyoll/dontek-aquatek-ha?style=for-the-badge" alt="Release"></a>
  <a href="https://github.com/jbyoll/dontek-aquatek-ha/actions/workflows/validate.yml"><img src="https://img.shields.io/github/actions/workflow/status/jbyoll/dontek-aquatek-ha/validate.yml?style=for-the-badge&label=validate" alt="Validate"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/jbyoll/dontek-aquatek-ha?style=for-the-badge" alt="License"></a>
</p>

---

Works with Dontek pool controllers sold under several brands — **Aquatek**, **Theralux
Pool+ Manager**, **Waterco Pooltek**, **Henden Control** and **Aquamate X** — which are the
same hardware with different labels.

> [!IMPORTANT]
> **This is an unofficial, community-built integration.** It is **not affiliated with,
> authorised by, or endorsed by Dontek Electronics**, and "Dontek", "Aquatek", "Theralux",
> "Pooltek" and related names are trademarks of their respective owners, used here only to
> describe compatibility. It was created by reverse-engineering the app's cloud traffic, uses
> **no official Dontek API**, and may stop working if Dontek change their backend. Use at your
> own risk. Tested against a single variable-speed-pump setup.

## ✨ Features

| | Entity | Details |
|---|---|---|
| 🌡️ | **Water temperature** | `sensor` — pool water temperature in °C |
| ⚙️ | **Pump mode status** | `sensor` — Off / On / Auto |
| 🏃 | **Pump activity** | `sensor` — live state: Running / Priming / Idle … |
| 🔢 | **Running speed** | `sensor` — the speed the pump is *actually* running at (1–4) |
| 🎛️ | **Pump mode** | `select` — set Off / On / Auto |
| 🏊 | **Pump speed** | `select` — set the default speed 1 / 2 / 3 / 4 |
| 📊 | **Speed 1–4 power** | `number` — tune each speed's power % |
| ⏱️ | **Filter 1–4 start / end** | `time` — each schedule window (all four filter times) |
| 🔁 | **Filter 1–4 enabled** | `switch` — turn each schedule on/off |
| 🏊 | **Filter 1–4 speed** | `select` — speed used by each schedule |

> In **Auto** mode the pump follows its filter schedule, so the live **Running speed** can
> differ from the **Pump speed** you set — just like the official app's status screen.

- ☁️ **No extra hardware** — talks to the Dontek cloud, works from anywhere.
- 🪶 **No heavy dependencies** — uses Home Assistant's built-in MQTT library and signs the
  AWS connection itself (no `boto3` / `awscrt`).
- 🔐 **Your account only** — anonymous cloud access, scoped to the controller you configure.

## 📦 Installation

### HACS (recommended)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jbyoll&repository=dontek-aquatek-ha&category=integration)

1. **HACS → ⋮ → Custom repositories** → add `jbyoll/dontek-aquatek-ha`, category **Integration**.
2. Install **Dontek Aquatek Pool Controller** and **restart Home Assistant**.
3. **Settings → Devices & Services → Add Integration → Dontek Aquatek**.

### Manual

Copy `custom_components/dontek_aquatek` into your Home Assistant `config/custom_components/`
folder and restart.

## ⚙️ Configuration

Add the integration from the UI and enter the **serial number** printed on the controller
label — the long number under the QR code, e.g. `56559560543361145`. You can also enter the
12-character MAC directly.

<p align="center"><img src="assets/icon.png" width="96" alt=""></p>

That's it — the device and its entities appear automatically.

## 🧭 How it works

The controller has **no local API**; on your LAN it only serves a Wi-Fi setup page, so all
control goes through Dontek's AWS cloud:

- **Auth** — an anonymous AWS **Cognito** identity pool (guest credentials, no login).
- **Transport** — AWS **IoT MQTT over WebSockets**, SigV4-signed. This integration signs the
  connection itself using Home Assistant's bundled `paho-mqtt`.
- **Protocol** — **Modbus-over-MQTT**: JSON messages
  `{"messageId":"read"|"write","modbusReg":R,"modbusVal":[…]}` on `dontek<mac>/cmd/psw`,
  with the controller replying on `dontek<mac>/status/psw`.

### Register map

| Reading / control | Register | Encoding |
|---|---|---|
| Water temperature | `57545` | °C = raw ÷ 256 |
| Pump mode | `65485` | `0` = Off · `1025` = On · `65535` = Auto |
| Pump speed (set/default) | `65463` | `0–3` → Speed 1–4 (display = value + 1) |
| Live run-state word | `92` | high byte = state (`12` = Running) · low byte = running speed (0–3) |
| Speed 1–4 power % | `65478`–`65481` | 0–100 % |
| Filter Time enable mask | `65318` | **bitmask** — bit 0 = FT1 … bit 3 = FT4 (`1` = FT1 only, `15` = all four) |
| Filter Time start / end | FT1 `65319`/`65320` · FT2 `65321`/`65322` · FT3 `65469`/`65470` · FT4 `65471`/`65472` | hour × 256 + minute (08:00 = 2048) |
| Filter Time speed | FT1 `65473` · FT2 `65474` · FT3 `65475` · FT4 `65476` | 0–3 → Speed 1–4 |
| Run Once (one-shot) | enable `57630` · start `57650` · end `57670` | mapped, not yet exposed as entities |

## 🔧 Troubleshooting

- **"Could not reach the controller"** when adding — double-check the serial number and that
  the controller is powered and online (it shows up in the official app).
- **Entities unavailable** — the integration polls the cloud every 30 s; a transient cloud or
  Wi-Fi drop clears on the next poll.
- Enable debug logging:
  ```yaml
  logger:
    logs:
      custom_components.dontek_aquatek: debug
  ```

## 🔒 Security note

Dontek's guest cloud policy is broad: any client that knows a controller's MAC can read and
write its registers, and the MAC is derived from the serial printed on the label. **Keep your
serial / QR code private.** This integration only communicates with the controller you set up.

## 🗺️ Roadmap

- [x] Map all four filter-time schedules (done in v0.4.0)
- [ ] Map remaining registers (flow, live RPM/power readback)
- [ ] `number` entities for the per-speed RPM setpoints
- [ ] Expose Run Once as a one-shot action/button
- [ ] Chlorinator / heater / lighting support on units that have them
- [ ] Multiple appliances / expansion modules
- [ ] Submit brand assets to [home-assistant/brands](https://github.com/home-assistant/brands)

## 🤝 Contributing

Issues and PRs welcome — especially register captures from **other Dontek models**. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

[MIT](LICENSE) © 2026 Jason Brandon · Not affiliated with Dontek Electronics.
