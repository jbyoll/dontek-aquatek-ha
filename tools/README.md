# Register capture tool

`dontek_capture.py` records what your controller reports and what the official app sends
when you press something. That is how new features get mapped (see
[CONTRIBUTING.md](../CONTRIBUTING.md)).

It connects to the Dontek cloud the same way the integration does, with an anonymous
guest login. It uses its own random client ID, so it won't knock your Home Assistant
integration offline while it runs.

## Setup

From the repo root, with Python 3.10+:

```
pip install paho-mqtt
```

The tool reuses the integration's own `dontek_client.py` and `const.py`, so run it from
inside a checkout of this repo.

## Running a capture

```
python tools/dontek_capture.py --serial <your serial> --out mycapture --redact \
    --model "Aquatek" --features "heater, VS pump, water feature"
```

| Option | What it does |
|---|---|
| `--serial` / `--mac` | Your controller. Use the same serial you gave the integration (the long number under the QR code), or the 12-character MAC. Spaces, dashes and colons are fine. |
| `--out` | Base name for the output files: `<out>.jsonl` and `<out>.md`. Runs append to an existing `.jsonl`, so delete old files or pick a new name. |
| `--redact` | Replaces your MAC and serial with `<mac>` / `<serial>` in both output files. Use it for anything you post. |
| `--model`, `--features` | Written into the summary so the issue has context. |
| `--interval` | Seconds between full register reads (default 8). Please don't go much lower. |
| `--baseline` | Reply chunks used to learn the "noisy" registers before diffing (default 8, about 4 polls). |
| `--wildcard` | Tries to subscribe to everything under `dontek<mac>/`. The guest login doesn't allow this today: AWS drops the connection, the tool says so once and carries on without it. Kept in case the policy changes. |
| `--no-color` | Plain output. Colour is also off when output isn't a terminal, or when `NO_COLOR` is set. |

### Step by step

1. Start the tool and leave the app alone for about 40 seconds. It learns which registers
   change on their own (clock, temperatures, run state).
2. When you see the green **ready** line, type a short note and press Enter **before**
   each action, e.g. `heater -> on`. That drops a marker and forces a fresh read.
3. Do the action in the controller's own app (Aquatek / Theralux / Pooltek). Leave about
   15 seconds between actions so each change lands under its own marker.
4. Press **Ctrl+C** when done. The tool writes the summary and prints both file names.
5. Open an issue and attach `<out>.jsonl` and `<out>.md`, plus a note of anything you
   mistyped. Screenshots of the app screens you used help too.

## Reading the console

```
07:35:03 --- MARK: setpoint -> 38
07:35:08 >>> APP write reg=65447 val=[76]
07:35:08       reg 65447: 0x004c  hi=0 lo=76  /256=0.30
07:35:09   reg 65447: 80 -> 76  0x004c  hi=0 lo=76  /256=0.30
```

- **Magenta `MARK`**: your note.
- **Yellow `>>> APP write`**: a write the app (or Home Assistant) sent to the
  controller. This is the most useful line: it gives the register and value directly.
  Each value is also shown decoded (hex, high/low byte, ÷256, and hh:mm when it could be
  a time).
- **`reg N: old -> new`**: registers that changed in the next read. Old values are red
  and new values green. Registers the integration already knows are labelled with their
  `const.py` name, and registers that change on their own are dimmed and tagged
  `(noisy)`.
- **Red warnings**: the tool explains the usual problems. For example, "no reply from
  the controller" almost always means the serial or MAC is wrong.

## Output files

- **`<out>.jsonl`**: every MQTT message, verbatim and timestamped, plus your markers. This
  is the raw record CONTRIBUTING asks for.
- **`<out>.md`**: a summary written on exit, ready to paste into an issue. It has the
  app's writes (each with the marker it followed), register changes grouped by marker,
  and the final full register dump in the read-all reply format.

## Things worth knowing

- The controller answers one read-all with **several MQTT messages** (seen: 563 + 9
  registers). The tool merges them, so there's no need to stitch them together by hand.
- **Appliances with their own app don't show up.** For example, a Waterco heat pump
  controlled from WatercoConnect has its own Wi-Fi module and cloud, so changes made there
  never reach the Dontek controller. Make changes in the controller's app while
  capturing.
- Home Assistant's writes appear as `>>> APP write` too, which makes the tool handy for
  checking that a new entity sends exactly what the app sends.
