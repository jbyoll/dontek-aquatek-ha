"""Lightweight client for Dontek pool controllers (Aquatek / Theralux / Pooltek).

Talks to Dontek's AWS IoT cloud exactly as the official app does:
  * anonymous AWS Cognito identity pool  -> temporary AWS credentials
  * AWS IoT MQTT over WebSockets (SigV4)  -> device "Modbus over MQTT"

Protocol (reverse engineered):
  command topic (publish):  dontek<mac>/cmd/psw
  status  topic (subscribe): dontek<mac>/status/psw
  message: {"messageId": "read"|"write", "modbusReg": <reg>, "modbusVal": [<u16>...]}
  read-all: publish {"messageId":"read","modbusReg":1,"modbusVal":[1]} ->
            device replies with a flat [reg,val,reg,val,...] register dump.

Only Home Assistant's bundled deps are used (paho-mqtt, plus stdlib + requests-style
HTTP via urllib). No boto3 / awscrt, so it installs cleanly everywhere HA runs.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable

import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

# Shared Dontek cloud constants (identical for every Aquatek/Theralux/Pooltek unit).
COGNITO_POOL_ID = "ap-southeast-2:c45f75ed-a7e5-4a4f-b27a-ac3941f6d9bf"
REGION = "ap-southeast-2"
IOT_ENDPOINT = "a219g53ny7vwvd-ats.iot.ap-southeast-2.amazonaws.com"
IOT_SERVICE = "iotdevicegateway"

COGNITO_HOST = f"cognito-identity.{REGION}.amazonaws.com"
_CREDS_TTL = 50 * 60  # refresh guest creds every 50 min (they last ~60)


def serial_to_mac(serial: str) -> str:
    """Convert the number printed/QR-encoded on the label to the device MAC.

    The app does: mac = ("%014x" % int(serial))[:12]  (lower-case hex, no colons).
    e.g. 56559560543361145 -> 'c8f09ee2d6d8'.
    """
    serial = str(serial).strip()
    return ("%014x" % int(serial))[:12].lower()


class CognitoError(Exception):
    """Raised when guest credentials cannot be obtained."""


def _cognito_call(target: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://{COGNITO_HOST}/",
        data=body,
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": f"AWSCognitoIdentityService.{target}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as err:  # noqa: BLE001 - surface a clean error to HA
        raise CognitoError(f"Cognito {target} failed: {err}") from err


def get_guest_credentials() -> dict:
    """Return temporary AWS creds from the unauthenticated identity pool."""
    ident = _cognito_call("GetId", {"IdentityPoolId": COGNITO_POOL_ID})
    identity_id = ident["IdentityId"]
    creds = _cognito_call(
        "GetCredentialsForIdentity", {"IdentityId": identity_id}
    )["Credentials"]
    return {
        "access_key": creds["AccessKeyId"],
        "secret_key": creds["SecretKey"],
        "token": creds["SessionToken"],
    }


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def build_signed_ws_path(creds: dict) -> str:
    """Build the SigV4-presigned WebSocket path for AWS IoT MQTT."""
    now = _dt.datetime.now(_dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    scope = f"{date_stamp}/{REGION}/{IOT_SERVICE}/aws4_request"
    cred_param = urllib.parse.quote(f"{creds['access_key']}/{scope}", safe="")

    q = (
        "X-Amz-Algorithm=AWS4-HMAC-SHA256"
        f"&X-Amz-Credential={cred_param}"
        f"&X-Amz-Date={amz_date}"
        "&X-Amz-SignedHeaders=host"
    )
    canonical_request = "\n".join(
        [
            "GET",
            "/mqtt",
            q,
            f"host:{IOT_ENDPOINT}\n",
            "host",
            hashlib.sha256(b"").hexdigest(),
        ]
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    k_date = _sign(("AWS4" + creds["secret_key"]).encode(), date_stamp)
    k_region = _sign(k_date, REGION)
    k_service = _sign(k_region, IOT_SERVICE)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(
        k_signing, string_to_sign.encode(), hashlib.sha256
    ).hexdigest()

    q += f"&X-Amz-Signature={signature}"
    if creds.get("token"):
        q += "&X-Amz-Security-Token=" + urllib.parse.quote(creds["token"], safe="")
    return f"/mqtt?{q}"


class DontekClient:
    """Maintains an MQTT session to one Dontek controller and exposes read/write."""

    def __init__(self, mac: str) -> None:
        self.mac = mac.lower()
        self.prefix = f"dontek{self.mac}"
        self.cmd_topic = f"{self.prefix}/cmd/psw"
        self.status_topic = f"{self.prefix}/status/psw"
        self.registers: dict[int, int] = {}
        self.connected = False
        self._client: mqtt.Client | None = None
        self._creds: dict | None = None
        self._creds_at = 0.0
        self._lock = threading.Lock()
        self._on_update: Callable[[dict[int, int]], None] | None = None

    def set_update_callback(self, cb: Callable[[dict[int, int]], None]) -> None:
        self._on_update = cb

    # -- connection -------------------------------------------------------
    def connect(self) -> None:
        with self._lock:
            self._creds = get_guest_credentials()
            self._creds_at = time.time()
            path = build_signed_ws_path(self._creds)
            client_id = "ha-dontek-" + hashlib.md5(self.mac.encode()).hexdigest()[:8]
            # paho-mqtt 2.x requires an explicit callback API version; fall back for 1.x.
            try:
                c = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION1,
                    client_id=client_id,
                    transport="websockets",
                )
            except (AttributeError, TypeError):
                c = mqtt.Client(client_id=client_id, transport="websockets")
            c.ws_set_options(path=path)
            c.tls_set()
            c.on_connect = self._on_connect
            c.on_message = self._on_message
            c.on_disconnect = self._on_disconnect
            c.connect(IOT_ENDPOINT, 443, keepalive=60)
            c.loop_start()
            self._client = c

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            try:
                self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
            self.connected = False

    def _on_connect(self, client, userdata, flags, rc):  # noqa: ANN001
        if rc == 0:
            self.connected = True
            client.subscribe(self.status_topic, qos=0)
            _LOGGER.debug("Dontek %s connected, subscribed %s", self.mac, self.status_topic)
            self.request_all()
        else:
            _LOGGER.warning("Dontek %s connect rc=%s", self.mac, rc)

    def _on_disconnect(self, client, userdata, rc):  # noqa: ANN001
        self.connected = False
        _LOGGER.debug("Dontek %s disconnected rc=%s", self.mac, rc)

    def _on_message(self, client, userdata, msg):  # noqa: ANN001
        try:
            d = json.loads(msg.payload.decode())
        except Exception:  # noqa: BLE001
            return
        if d.get("messageId") != "read":
            return
        vals = d.get("modbusVal") or []
        if len(vals) <= 2:
            return
        changed = {}
        for i in range(0, len(vals) - 1, 2):
            reg, val = vals[i], vals[i + 1]
            self.registers[reg] = val
            changed[reg] = val
        if self._on_update:
            self._on_update(changed)

    # -- credential refresh ----------------------------------------------
    def _ensure_fresh(self) -> None:
        if time.time() - self._creds_at > _CREDS_TTL or not self.connected:
            _LOGGER.debug("Dontek %s refreshing session", self.mac)
            self.disconnect()
            self.connect()
            time.sleep(2)

    # -- protocol ---------------------------------------------------------
    def _publish(self, payload: dict) -> None:
        self._ensure_fresh()
        if self._client:
            self._client.publish(self.cmd_topic, json.dumps(payload), qos=0)

    def request_all(self) -> None:
        """Ask the controller to dump its full register table."""
        if self._client:
            self._client.publish(
                self.cmd_topic,
                json.dumps({"messageId": "read", "modbusReg": 1, "modbusVal": [1]}),
                qos=0,
            )

    def write_register(self, reg: int, value: int) -> None:
        """Write a single 16-bit register, then re-read state."""
        self._publish({"messageId": "write", "modbusReg": int(reg), "modbusVal": [int(value)]})
        time.sleep(0.5)
        self.request_all()
