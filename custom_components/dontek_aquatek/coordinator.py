"""DataUpdateCoordinator wrapping the Dontek MQTT client."""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .dontek_client import DontekClient

_LOGGER = logging.getLogger(__name__)


class DontekCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Keeps a live MQTT session and periodically refreshes the register table."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, mac: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{mac}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.mac = mac
        self.client = DontekClient(mac)

    async def async_connect(self) -> None:
        """Open the MQTT session (runs the blocking client in the executor)."""
        def _connect() -> None:
            self.client.connect()
            for _ in range(20):
                if self.client.connected:
                    break
                time.sleep(0.5)

        await self.hass.async_add_executor_job(_connect)

    async def async_shutdown(self) -> None:
        await self.hass.async_add_executor_job(self.client.disconnect)

    async def _async_update_data(self) -> dict[int, int]:
        """Request a fresh register read and return the table.

        We require a *new* status reply each cycle (tracked via
        ``client.last_update``) rather than trusting the ``connected`` flag or a
        non-empty register cache: AWS IoT can drop the websocket without a clean
        disconnect, which would otherwise leave us publishing into a dead socket
        and silently serving stale values forever.
        """
        def _poll_once(timeout: float = 12.0) -> bool:
            """Request a dump and wait for a reply newer than before. True if fresh."""
            prev = self.client.last_update
            self.client.request_all()
            deadline = time.monotonic() + timeout
            while self.client.last_update <= prev:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.5)
            return True

        def _refresh() -> dict[int, int]:
            # reconnect up front if the session looks down or creds are stale
            self.client.ensure_session()
            if not _poll_once():
                # no fresh reply -> the connection is dead; rebuild and retry once
                self.client.reconnect()
                if not _poll_once():
                    raise UpdateFailed("No fresh reply from the Dontek cloud")
            return dict(self.client.registers)

        try:
            regs = await self.hass.async_add_executor_job(_refresh)
        except UpdateFailed:
            raise
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error talking to Dontek cloud: {err}") from err
        if not regs:
            raise UpdateFailed("No register data received from controller yet")
        return regs

    async def async_write_register(self, reg: int, value: int) -> None:
        await self.hass.async_add_executor_job(self.client.write_register, reg, value)
        await self.async_request_refresh()
