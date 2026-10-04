"""Config flow for Dontek Aquatek."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_MAC, CONF_NAME, CONF_SERIAL, DEFAULT_NAME, DOMAIN
from .dontek_client import DontekClient, serial_to_mac


class DontekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dontek Aquatek."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = str(user_input[CONF_SERIAL]).strip()
            try:
                # Accept either the printed serial number or the 12-char MAC directly.
                if raw.isdigit():
                    mac = serial_to_mac(raw)
                else:
                    mac = raw.replace(":", "").replace("-", "").lower()
                if len(mac) != 12 or not all(c in "0123456789abcdef" for c in mac):
                    raise ValueError("bad mac")
            except Exception:  # noqa: BLE001
                errors["base"] = "invalid_serial"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                # Verify we can actually reach the controller before creating the entry.
                ok = await self.hass.async_add_executor_job(_test_connection, mac)
                if not ok:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                        data={
                            CONF_MAC: mac,
                            CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


def _test_connection(mac: str) -> bool:
    """Blocking: connect briefly and confirm the controller answers."""
    import time

    client = DontekClient(mac)
    try:
        client.connect()
        for _ in range(15):
            if client.registers:
                return True
            time.sleep(1)
        return False
    except Exception:  # noqa: BLE001
        return False
    finally:
        client.disconnect()
