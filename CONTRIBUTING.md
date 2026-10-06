# Contributing

Thanks for helping improve this **unofficial** Dontek integration! Contributions are very
welcome — especially data from controllers other than the one it was built on.

## Most useful contribution: register captures

Different Dontek models and feature sets (chlorinator, heater, lighting, multiple pumps,
expansion modules) expose different registers. If you can capture what your controller
reports and what the app sends when you press a button, we can map more features.

The protocol is **Modbus-over-MQTT** on these topics (lower-case MAC, no colons):

- publish commands to `dontek<mac>/cmd/psw`
- subscribe to `dontek<mac>/status/psw`
- message shape: `{"messageId":"read"|"write","modbusReg":<reg>,"modbusVal":[<u16>...]}`

The easiest way is the capture tool (needs only `pip install paho-mqtt`):

```
python tools/dontek_capture.py --serial <your serial> --out mycapture --redact     --model "Aquatek" --features "heater, VS pump"
```

Wait for the green **ready** line, then type a short note + Enter before each thing you
press in the app. Ctrl+C writes `mycapture.jsonl` (raw log) and `mycapture.md` (summary of
the app's writes and register changes) — attach both. Full usage notes are in
[tools/README.md](tools/README.md). Some appliances also have their own
app and Wi-Fi module (e.g. Waterco heat pumps with **WatercoConnect**) on a separate
cloud; changes made there never reach the controller, so make changes in the controller's
own app (Aquatek / Theralux / **Pooltek**) while capturing.

When opening an issue with a capture, please include:

- your controller model / brand and what features it has,
- a full register dump (publish `{"messageId":"read","modbusReg":1,"modbusVal":[1]}`),
- the `write` messages the app sends for a given action, with a note of what you pressed.

Please **redact your serial / MAC** in anything you post publicly.

## Code

- Keep runtime dependencies to what Home Assistant already bundles where possible.
- Run the checks locally before a PR: the repo's GitHub Actions run **hassfest** and the
  **HACS** validator on every push.
- Use clear, conventional commit messages.

## Scope & safety

This project only reads and writes the controller the user configures. Please don't add
anything that scans for or touches other people's devices.
