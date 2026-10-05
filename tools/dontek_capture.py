#!/usr/bin/env python3
"""Register capture tool for Dontek controllers (Aquatek / Theralux / Pooltek).

Sniffs both MQTT topics for one controller so you can see exactly what the
official app writes, and diffs full register dumps around each action.

  * logs every app write seen on  dontek<mac>/cmd/psw
  * polls full dumps from          dontek<mac>/status/psw and diffs them
  * learns "noisy" registers (clock, temp, run-state) during a baseline
  * type a note + Enter at any time to drop a marker and force a dump

Outputs (see CONTRIBUTING.md):
  <out>.jsonl  every raw MQTT message verbatim + markers (attach to an issue)
  <out>.md     summary written on exit: app writes, diffs per marker, full dump
  console      colourised, human-readable view of the same

Usage (from the repo root, needs only paho-mqtt):
    python tools/dontek_capture.py --serial 5655...145 --out heater --redact \\
        --model "Aquatek" --features "heater (gas), VS pump"
    python tools/dontek_capture.py --mac c8f09ee2d6d8 --interval 5 --no-color
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import threading
import time
import uuid

import paho.mqtt.client as mqtt

_PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "custom_components", "dontek_aquatek")


def _load(name: str):
    # load by path: putting _PKG on sys.path would let its select.py/time.py
    # shadow the stdlib modules paho needs
    spec = importlib.util.spec_from_file_location(name, os.path.join(_PKG, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


const = _load("const")
_client = _load("dontek_client")
IOT_ENDPOINT = _client.IOT_ENDPOINT
build_signed_ws_path = _client.build_signed_ws_path
get_guest_credentials = _client.get_guest_credentials
serial_to_mac = _client.serial_to_mac

READ_ALL = {"messageId": "read", "modbusReg": 1, "modbusVal": [1]}
CREDS_TTL = 45 * 60


def _known_registers() -> dict[int, str]:
    """reg -> constant name(s) from const.py, so diffs show what's already mapped."""
    names: dict[int, list[str]] = {}

    def add(reg: int, name: str) -> None:
        names.setdefault(reg, []).append(name)

    for name, val in vars(const).items():
        if not name.startswith("REG_"):
            continue
        if isinstance(val, int):
            add(val, name)
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(v, int):
                    add(v, f"{name}[{k}]")
    for n, regs in const.FILTER_TIMES.items():
        for field, reg in regs.items():
            add(reg, f"FT{n}_{field}")
    return {r: "/".join(dict.fromkeys(n)) for r, n in names.items()}


KNOWN = _known_registers()


class Style:
    """Minimal ANSI colouring; disabled with --no-color, NO_COLOR or a non-tty."""

    def __init__(self, enabled: bool) -> None:
        self.on = enabled
        if enabled and os.name == "nt":
            os.system("")  # enables VT100 escape handling in the Windows console

    def __call__(self, text: str, *codes: str) -> str:
        if not self.on:
            return text
        table = {"bold": "1", "dim": "2", "red": "31", "green": "32",
                 "yellow": "33", "blue": "34", "magenta": "35", "cyan": "36",
                 "grey": "90"}
        return "\033[" + ";".join(table[c] for c in codes) + "m" + text + "\033[0m"


def decode(val: int) -> str:
    """Show the encodings we've seen on this controller so far."""
    hi, lo = val >> 8, val & 0xFF
    parts = [f"0x{val:04x}", f"hi={hi} lo={lo}", f"/256={val / 256:.2f}"]
    if hi <= 23 and lo <= 59:
        parts.append(f"time?={hi:02d}:{lo:02d}")
    if val >= 0x8000:
        parts.append(f"s16={val - 0x10000}")
    return "  ".join(parts)


class Capture:
    def __init__(self, mac: str, out: str, interval: float, baseline: int,
                 redact: bool, serial: str | None, model: str, features: str,
                 style: Style, wildcard: bool = False) -> None:
        self.mac = mac
        self.serial = serial
        self.cmd = f"dontek{mac}/cmd/psw"
        self.status = f"dontek{mac}/status/psw"
        self.wildcard = f"dontek{mac}/#" if wildcard else None
        self.wildcard_ok = False
        self.interval = interval
        self.baseline_left = baseline
        self.redact = redact
        self.model = model
        self.features = features
        self.s = style
        base = out[:-6] if out.endswith(".jsonl") else out
        self.jsonl_path = base + ".jsonl"
        self.md_path = base + ".md"
        self.fh = open(self.jsonl_path, "a", encoding="utf-8")
        self.prev: dict[int, int] = {}
        self.last_raw_dump: str | None = None
        self.first_dump: dict[int, int] = {}
        self.noisy: set[int] = set()
        self.mark = "(before first marker)"
        self.app_cmds: list[tuple[str, str, dict]] = []
        self.diffs: list[tuple[str, str, dict[int, list]]] = []
        self.sub_mids: dict[int, list[str]] = {}
        self.client: mqtt.Client | None = None
        self.creds_at = 0.0
        self.polls_unanswered = 0
        self.lock = threading.Lock()

    # -- output -----------------------------------------------------------
    def scrub(self, text: str) -> str:
        if self.redact:
            text = text.replace(self.mac, "<mac>")
            if self.serial:
                text = text.replace(self.serial, "<serial>")
        return text

    def log(self, kind: str, **data) -> None:
        rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, **data}
        with self.lock:
            self.fh.write(self.scrub(json.dumps(rec)) + "\n")
            self.fh.flush()

    def say(self, text: str) -> None:
        stamp = self.s(time.strftime("%H:%M:%S"), "grey")
        with self.lock:
            print(f"{stamp} {text}", flush=True)

    def reg_label(self, reg: int) -> str:
        name = KNOWN.get(reg)
        return f"{reg:>5}" + (self.s(f" ({name})", "blue") if name else "")

    # -- mqtt -------------------------------------------------------------
    def connect(self) -> None:
        if self.client is not None:
            threading.Thread(target=self.client.loop_stop, daemon=True).start()
            try:
                self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        creds = get_guest_credentials()
        self.creds_at = time.time()
        # unique client id: reusing HA's id would kick the integration offline
        cid = "capture-" + uuid.uuid4().hex[:10]
        try:
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=cid,
                            transport="websockets")
        except (AttributeError, TypeError):
            c = mqtt.Client(client_id=cid, transport="websockets")
        c.ws_set_options(path=build_signed_ws_path(creds))
        c.tls_set()
        c.on_connect = self.on_connect
        c.on_disconnect = self.on_disconnect
        c.on_subscribe = self.on_subscribe
        c.on_message = self.on_message
        c.connect(IOT_ENDPOINT, 443, keepalive=60)
        c.loop_start()
        self.client = c

    def on_connect(self, client, userdata, flags, rc):  # noqa: ANN001
        if rc != 0:
            self.say(self.s(f"connect failed rc={rc}", "red", "bold"))
            return
        self.say(self.s(f"connected, watching {self.scrub(self.cmd)} + "
                        f"{self.scrub(self.status)}", "cyan"))
        # subscribe separately so a refused cmd topic is reported on its own
        for topic in (self.status, self.cmd) + ((self.wildcard,) if self.wildcard else ()):
            _, mid = client.subscribe(topic, 0)
            self.sub_mids[mid] = [topic]

    def on_subscribe(self, client, userdata, mid, granted_qos):  # noqa: ANN001
        topic = self.sub_mids.pop(mid, ["?"])[0]
        ok = all(q != 128 for q in granted_qos)
        self.log("subscribe", topic=topic, granted=list(granted_qos))
        if topic == self.wildcard:
            self.wildcard_ok = ok
        if ok:
            self.say(self.s(f"subscribed {self.scrub(topic)}", "cyan"))
        elif topic == self.cmd:
            self.say(self.s("cmd topic subscription REFUSED - app writes won't be "
                            "visible; fall back to marker + dump diffs", "red", "bold"))
        else:
            self.say(self.s(f"subscription REFUSED: {self.scrub(topic)}", "red", "bold"))

    def on_disconnect(self, client, userdata, rc):  # noqa: ANN001
        if self.wildcard and not self.wildcard_ok:
            # AWS IoT drops the connection on an unauthorised subscribe rather
            # than refusing it in the SUBACK; stop asking or we loop forever
            self.log("subscribe", topic=self.wildcard, granted="dropped")
            self.say(self.s("AWS dropped the connection on the wildcard subscribe - "
                            "the guest policy doesn't allow it; continuing "
                            "without --wildcard", "red", "bold"))
            self.wildcard = None
            return
        if rc != 0:
            self.say(self.s(f"disconnected rc={rc} (paho will retry)", "yellow"))

    def request_dump(self) -> None:
        if self.client:
            self.client.publish(self.cmd, json.dumps(READ_ALL), qos=0)

    def on_message(self, client, userdata, msg):  # noqa: ANN001
        raw = msg.payload.decode(errors="replace")
        # raw record of everything, verbatim - this is what CONTRIBUTING asks for
        self.log("mqtt", topic=msg.topic, payload=raw)
        if msg.topic not in (self.cmd, self.status):
            # only reachable with --wildcard: another subsystem under this MAC
            self.say(self.s(f"*** OTHER TOPIC {self.scrub(msg.topic)}: {raw[:300]}",
                            "magenta", "bold"))
            return
        try:
            d = json.loads(raw)
        except ValueError:
            self.say(self.s(f"non-JSON on {self.scrub(msg.topic)}: {raw[:80]}", "yellow"))
            return
        if msg.topic == self.cmd:
            if d == READ_ALL:
                return  # our polls, HA's polls or the app's - all just noise
            self.handle_app_cmd(d)
            return
        vals = d.get("modbusVal") or []
        if d.get("messageId") == "read" and len(vals) > 2:
            self.polls_unanswered = 0
            self.last_raw_dump = raw
            self.handle_dump(dict(zip(vals[0::2], vals[1::2])))
        else:
            self.say(self.s(f"status: {raw}", "dim"))

    def handle_app_cmd(self, d: dict) -> None:
        # anything else on cmd came from the app (or HA) - gold dust
        kind = d.get("messageId")
        reg = d.get("modbusReg")
        vals = d.get("modbusVal") or []
        self.app_cmds.append((time.strftime("%H:%M:%S"), self.mark, d))
        colour = ("yellow", "bold") if kind == "write" else ("magenta",)
        self.say(self.s(f">>> APP {kind} reg={reg} val={vals}", *colour)
                 + (self.s(f"  ({KNOWN[reg]})", "blue") if reg in KNOWN else ""))
        for i, v in enumerate(vals):
            if isinstance(v, int):
                tag = f"reg {reg + i}" if isinstance(reg, int) else "val"
                self.say(f"      {tag}: {decode(v)}")

    def handle_dump(self, regs: dict[int, int]) -> None:
        # The controller answers one read-all with several messages (seen: 563 +
        # 9 registers), so treat each as a partial update of one merged map.
        if not self.prev:
            self.say(self.s(f"first dump chunk: {len(regs)} registers, learning "
                            f"noisy registers over {self.baseline_left} more "
                            "chunks...", "cyan"))
        new = {r: v for r, v in regs.items() if r not in self.prev}
        diff = {r: [self.prev[r], v] for r, v in regs.items()
                if r in self.prev and self.prev[r] != v}
        self.prev.update(regs)
        if self.baseline_left > 0:
            self.first_dump.update(new)
            self.noisy |= set(diff)
            self.baseline_left -= 1
            if self.baseline_left == 0:
                self.log("noisy", regs=sorted(self.noisy))
                self.say(self.s(f"baseline done: {len(self.prev)} registers, "
                                f"noisy: {sorted(self.noisy)}", "cyan"))
                self.say(self.s("ready - type a note + Enter before each app "
                                "action (Ctrl+C to finish)", "green", "bold"))
            return
        diff.update({r: [None, v] for r, v in new.items()})
        if not diff:
            return
        self.diffs.append((time.strftime("%H:%M:%S"), self.mark, diff))
        self.log("diff", mark=self.mark,
                 changes={str(r): ov for r, ov in sorted(diff.items())})
        for r, (old, val) in sorted(diff.items()):
            noisy = r in self.noisy
            line = (f"  reg {self.reg_label(r)}: "
                    f"{self.s(str(old), 'dim' if noisy else 'red')} -> "
                    f"{self.s(str(val), 'dim' if noisy else 'green')}"
                    f"  {self.s(decode(val), 'grey')}")
            self.say(self.s(line + "  (noisy)", "dim") if noisy else line)

    # -- report -----------------------------------------------------------
    def merged_dump(self) -> str:
        if not self.prev:
            return "(none received)"
        flat = [x for r in sorted(self.prev) for x in (r, self.prev[r])]
        return json.dumps({"messageId": "read", "modbusReg": 1, "modbusVal": flat})

    def write_report(self) -> None:
        L = [f"# Dontek register capture ({time.strftime('%Y-%m-%d %H:%M')})", "",
             f"- **Controller model / brand:** {self.model or '_fill me in_'}",
             f"- **Features:** {self.features or '_fill me in_'}",
             f"- **Raw log:** `{os.path.basename(self.jsonl_path)}` (attach this too)",
             f"- **Noisy registers (changed with nobody touching anything):** "
             f"{sorted(self.noisy) or 'n/a'}", "",
             "## Writes sent by the app", ""]
        if self.app_cmds:
            L += ["| time | after marker | message |", "|---|---|---|"]
            L += [f"| {t} | {m} | `{json.dumps(d)}` |" for t, m, d in self.app_cmds]
        else:
            L.append("_none seen_")
        L += ["", "## Register changes per marker", ""]
        by_mark: dict[str, dict[int, list]] = {}
        for _, m, diff in self.diffs:
            agg = by_mark.setdefault(m, {})
            for r, (old, new) in diff.items():
                agg.setdefault(r, [old, new])[1] = new
        for m, agg in by_mark.items():
            L += [f"### {m}", "", "| reg | known as | old | new | decode |",
                  "|---|---|---|---|---|"]
            for r, (old, new) in sorted(agg.items()):
                flag = " (noisy)" if r in self.noisy else ""
                L.append(f"| {r}{flag} | {KNOWN.get(r, '')} | {old} | {new} | "
                         f"{decode(new) if isinstance(new, int) else ''} |")
            L.append("")
        if not by_mark:
            L += ["_no changes outside the baseline_", ""]
        if self.prev:
            added = sorted(set(self.prev) - set(self.first_dump))
            if added:
                L += [f"Registers that appeared during the session: {added}", ""]
        L += ["## Full register dump (last received)", "",
              "Reply to `{\"messageId\":\"read\",\"modbusReg\":1,\"modbusVal\":[1]}`:",
              "(merged from all reply chunks; raw chunks are in the .jsonl)", "",
              "```json", self.merged_dump(), "```", ""]
        with open(self.md_path, "w", encoding="utf-8") as fh:
            fh.write(self.scrub("\n".join(L)))

    # -- main loop --------------------------------------------------------
    def stdin_markers(self) -> None:
        for line in sys.stdin:
            note = line.strip()
            if note:
                self.mark = note
                self.say(self.s(f"--- MARK: {note} ", "magenta", "bold"))
                self.log("mark", note=note)
                self.request_dump()

    def run(self) -> None:
        self.log("session", model=self.model, features=self.features,
                 interval=self.interval, redacted=self.redact)
        self.connect()
        threading.Thread(target=self.stdin_markers, daemon=True).start()
        time.sleep(3)
        try:
            while True:
                if time.time() - self.creds_at > CREDS_TTL:
                    self.say(self.s("refreshing credentials", "cyan"))
                    self.connect()
                    time.sleep(3)
                self.request_dump()
                self.polls_unanswered += 1
                if self.polls_unanswered == 3 and not self.prev:
                    self.say(self.s(
                        f"no reply from the controller on {self.scrub(self.status)} "
                        "- MAC is probably wrong (use the same serial as in HA) "
                        "or the unit is offline", "red", "bold"))
                time.sleep(self.interval)
        except KeyboardInterrupt:
            pass
        self.log("dump_final", payload=self.merged_dump())
        self.write_report()
        print(self.s(f"\nstopped - raw log: {self.jsonl_path}  summary: "
                     f"{self.md_path}", "green", "bold"))
        if not self.redact:
            print(self.s("note: not redacted - re-run with --redact or scrub your "
                         "MAC before posting", "yellow"))


def resolve_mac(serial: str | None, mac: str | None,
                p: argparse.ArgumentParser) -> str:
    """Accept the decimal label serial or a MAC, tolerating spaces/dashes/colons."""
    raw = (serial or mac or "").strip()
    cleaned = "".join(ch for ch in raw if ch not in " -:._").lower()
    if serial and cleaned.isdigit():
        return serial_to_mac(cleaned)
    if len(cleaned) == 12 and all(ch in "0123456789abcdef" for ch in cleaned):
        if serial:
            print("note: --serial looks like a MAC, using it as one")
        return cleaned
    p.error(f"couldn't read {raw!r}: --serial wants the all-digit number under "
            "the QR code (e.g. 56559560543361145); --mac wants 12 hex chars")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--serial", help="number under the QR code on the label")
    g.add_argument("--mac", help="12-char MAC, lower-case, no colons")
    p.add_argument("--out", default="dontek_capture",
                   help="output base name -> <out>.jsonl + <out>.md")
    p.add_argument("--interval", type=float, default=8.0,
                   help="seconds between full dumps (be gentle, default 8)")
    p.add_argument("--baseline", type=int, default=8,
                   help="reply chunks used to learn noisy registers (~2 per poll)")
    p.add_argument("--redact", action="store_true",
                   help="replace the MAC/serial with <mac>/<serial> in output files")
    p.add_argument("--model", default="", help="controller model/brand for the report")
    p.add_argument("--features", default="",
                   help="e.g. 'gas heater, VS pump, chlorinator'")
    p.add_argument("--wildcard", action="store_true",
                   help="also subscribe to dontek<mac>/# to find other subsystems")
    p.add_argument("--no-color", action="store_true", help="plain console output")
    a = p.parse_args()
    mac = resolve_mac(a.serial, a.mac, p)
    colour = (not a.no_color and "NO_COLOR" not in os.environ
              and sys.stdout.isatty())
    Capture(mac, a.out, a.interval, a.baseline, a.redact,
            a.serial.strip() if a.serial else None, a.model, a.features,
            Style(colour), a.wildcard).run()


if __name__ == "__main__":
    main()
