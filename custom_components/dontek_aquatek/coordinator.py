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
        """Trigger a fresh register read and return the current table."""
        def _refresh() -> dict[int, int]:
            if not self.client.connected:
                self.client.connect()
                # give the broker a moment to establish + subscribe
                for _ in range(20):
                    if self.client.connected:
                        break
                    time.sleep(0.5)
            self.client.request_all()
            # wait for the controller's status reply to populate registers
            for _ in range(20):
                if self.client.registers:
                    break
                time.sleep(0.5)
            return self.client.registers

        try:
            regs = await self.hass.async_add_executor_job(_refresh)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error talking to Dontek cloud: {err}") from err
        if not regs:
            raise UpdateFailed("No register data received from controller yet")
        return regs

    async def async_write_register(self, reg: int, value: int) -> None:
        await self.hass.async_add_executor_job(self.client.write_register, reg, value)
        await self.async_request_refresh()
