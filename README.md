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

Works with Dontek pool controllers sold under several brands — **Aquatek**, **Oasis Smart**, **Theralux
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
| 🔥 | **Heater** | `climate` — Off / Heat, target temperature (0.5 °C steps; follows Pool / Spa mode, using the spa setpoint while in Spa), heating/idle *(disabled by default; enable it if you have a heater)* |
| ♨️ | **Run til heated** | `switch` (config) — setting: heater switches off once the setpoint is reached instead of staying on *(disabled by default)* |
| 🔌 | **Filter pump mode** | `select` — Off / On / Auto for **Socket 1**, whatever it's set to in the app (usually the filter pump, but it can be e.g. a pool light) |
| 🔌 | **Socket 2–8** | `select` — Off / On / Auto for each socket, named after the socket's name in the app or its appliance type (e.g. *Socket 2 Robot*). Sockets set to *Always On* show On but can't be switched (same as the app); sockets set to *None* are unavailable |
| 🛠️ | **Socket 1–8 type** / **name** | `select` / `text` (config) — change a socket's appliance type and its 16-character name, the same settings as the app's Appliance Setup. ⚠️ Changing a socket's type turns it Off |
| 🟢 | **Socket 1–8 running** | `binary_sensor` — whether each socket is energised right now. Unavailable when no appliance is assigned. For a variable-speed pump this is the relay feeding the pump, so it can read *running* while the pump itself is idle |
| 🚰 | **Valve 1–4** | `binary_sensor` — state of each valve that has a function assigned in the app (e.g. *Valve 1 Pool/Spa* is on while in Spa) |
| 🚿 | **Valve 1–4 switch** | `switch` — turn a valve on/off, for each valve with a function other than *Pool/Spa* (those follow **Pool / Spa mode**). Named by type, e.g. *Valve 3 Water Feature*. Enabled by default for *Water Feature*, *Feature from Solar* and *Other*; created disabled for *Solar*, *In Floor* and *Heating*, which the controller moves itself |
| 🛁 | **Pool / Spa mode** | `select` — switch between pool and spa. Enabled by default on an Aquatek with **Spa Enabled** turned on in the app's Spa Setup; otherwise created disabled |
| 🌞 | **Roof temperature** / **Solar pump** | `sensor` / `binary_sensor` — roof sensor and solar pump flag *(Oasis only, disabled by default)* |
| ⛲ | **Water feature** | `switch` — since v0.14 this is the switch of the valve typed *Water Feature* (or of valve 2 if none is), keeping the same entity id. Only when no valve switch can take it over is it still the old fixed switch on register `65345` (valve 2) *(disabled by default)* |

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
| Water temperature | `79` (fallback `57545`) | °C = raw ÷ 2 (fallback: raw ÷ 256) |
| Pump mode (Hayward VSP) | `65485` | `0` = Off · `1025` = On · `65535` = Auto |
| Socket 1–8 mode | `65336`–`65343` | `0` = Off · `1` = On · `2` = Auto (`65336` = Socket 1 / Filter pump) |
| Socket 1–8 appliance type | `65323`–`65330` | index into the app's list: `0` None · `1` Sanitiser · `2` Filter Pump · `3` Cleaning Pump · `4` Blower · `5` Pool Light · `6` Spa Light · `7` Garden Light · `8` Water Feature · `9` Solar · `10` Other · `11` Always On · `12` Jet Pump · `13` Heating Pump (ind.) · `14` UV Sanitiser |
| Socket 1–8 name | 8 registers each from `57344` (Socket n = `57344 + 8 × (n − 1)`) | ASCII, 2 characters per register, max 16. The app writes all 8 in one message, zero padded; empty = all `0` |
| Socket 1–8 running (live) | `160`–`167` | `0` = off · `1` = running · `2` = no appliance assigned |
| Valve 1–4 type | `65331`–`65334` | `0` None · `1` Pool/Spa · `2` Solar · `3` Water Feature · `4` In Floor · `5` Feature from Solar · `6` Other · `7` Heating |
| Valve 1–4 mode | `65344`–`65347` | `0` = Off · `1` = On (an Oasis app turns a Water Feature valve 3 on/off by writing `65346`) |
| Valve 1–4 state (live) | `168`–`171` | `0` / `1` (`1` = switched, e.g. Spa) · `2` = not assigned |
| Output layout | — | 13 outputs in order (sockets 1–8, valves 1–4, VF contact): type `65323 + i`, mode `65336 + i`, live flag `160 + i`. The heater (`65348` / `172`) is the VF contact |
| Pool / Spa mode | `65313` | `0` = Pool · `1` = Spa |
| Spa enabled (Spa Setup) | `65482` | `0` / `1` |
| Pump speed (set/default) | `65463` | `0–3` → Speed 1–4 (display = value + 1) |
| Live run-state word | `92` | high byte = state (`12` = Running) · low byte = running speed (0–3) |
| Speed 1–4 power % | `65478`–`65481` | 0–100 % |
| Filter Time enable mask | `65318` | **bitmask** — bit 0 = FT1 … bit 3 = FT4 (`1` = FT1 only, `15` = all four) |
| Filter Time start / end | FT1 `65319`/`65320` · FT2 `65321`/`65322` · FT3 `65469`/`65470` · FT4 `65471`/`65472` | hour × 256 + minute (08:00 = 2048) |
| Filter Time speed | FT1 `65473` · FT2 `65474` · FT3 `65475` · FT4 `65476` | 0–3 → Speed 1–4 |
| Heater on/off | `65348` | `0` = Off · `1` = On (no Auto in the app) |
| Heater setpoint (pool) | `65447` | °C × 2 (`80` = 40.0 °C) |
| Heater setpoint (spa) | `65441` | °C × 2 (`74` = 37.0 °C); used while Pool/Spa mode is Spa |
| Run til heated (setting) | `65500` | `0` / `1` |
| Heater active (calling for heat) | `172` | `0` / `1` (`2` seen on a unit with no heater) |
| Water feature (legacy) | `65345` | valve 2's mode; see Valve 1–4 mode |
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
- [x] Filter Pump (Socket 1) control (done in v0.5.0)
- [x] Brand icons — shipped in the integration's `brand/` folder, served via Home
  Assistant's local brand proxy (home-assistant/brands no longer accepts custom
  integrations as of HA 2026.3)
- [ ] Map remaining registers (flow, live RPM/power readback)
- [ ] `number` entities for the per-speed RPM setpoints
- [x] Expose Run Once as a one-shot action/button (done in v0.6.0)
- [x] Heater (on/off + setpoint), Run til heated, Water feature (done in v0.7.0)
- [ ] Chlorinator / lighting support on units that have them
- [x] Expansion sockets (Off / On / Auto for sockets 2–5) and Pool / Spa mode on Aquatek
- [x] Valve state and on/off switches (done in v0.12.0 / v0.14.0), separate pool / spa heater setpoints (done in v0.12.0)

## 🤝 Contributing

Issues and PRs welcome — especially register captures from **other Dontek models**. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

[MIT](LICENSE) © 2026 Jason Brandon · Not affiliated with Dontek Electronics.
