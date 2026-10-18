"""DataUpdateCoordinator wrapping the Dontek MQTT client."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REG_CLOCK_HOUR,
    REG_CLOCK_MIN,
    REG_RUNONCE_ENABLE,
    REG_RUNONCE_END,
    REG_RUNONCE_START,
    RUNONCE_DEFAULT_MIN,
    hm_to_reg,
)
from .dontek_client import DontekClient, DontekWriteError

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
        # HA-side Run Once duration (minutes); the number entity persists it.
        self.run_once_minutes = RUNONCE_DEFAULT_MIN
        # held by the executor thread for a whole refresh, so a refresh left
        # running past the timeout can't overlap the next one
        self._refresh_lock = threading.Lock()

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
        await super().async_shutdown()
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
            # The controller answers one read-all in several messages (seen: two,
            # ~0.3 s apart). Wait until they stop arriving so the table we return
            # is complete - entity setup reads it once, on the first refresh.
            settle_deadline = time.monotonic() + 3.0
            while (
                time.monotonic() - self.client.last_update < 1.0
                and time.monotonic() < settle_deadline
            ):
                time.sleep(0.2)
            return True

        def _refresh() -> dict[int, int]:
            if not self._refresh_lock.acquire(blocking=False):
                raise UpdateFailed("Previous refresh is still running")
            try:
                # reconnect up front if the session looks down or creds are stale
                self.client.ensure_session()
                if not _poll_once():
                    # no fresh reply -> the connection is dead; rebuild and retry once
                    self.client.reconnect()
                    if not _poll_once():
                        raise UpdateFailed("No fresh reply from the Dontek cloud")
                return dict(self.client.registers)
            finally:
                self._refresh_lock.release()

        try:
            # hard ceiling so a wedged network thread can never stall the
            # coordinator indefinitely (the executor thread is abandoned, the
            # next interval retries with a fresh session).
            async with asyncio.timeout(50):
                regs = await self.hass.async_add_executor_job(_refresh)
        except UpdateFailed:
            raise
        except (asyncio.TimeoutError, TimeoutError) as err:
            raise UpdateFailed("Timed out talking to the Dontek cloud") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error talking to Dontek cloud: {err}") from err
        if not regs:
            raise UpdateFailed("No register data received from controller yet")
        return regs

    async def _async_run_write(self, func, *args) -> None:  # noqa: ANN001
        """Run a blocking write in the executor; show send failures in the UI."""
        try:
            await self.hass.async_add_executor_job(func, *args)
        except DontekWriteError as err:
            raise HomeAssistantError(f"Could not send to the pool controller: {err}") from err
        await self.async_request_refresh()

    async def async_write_register(self, reg: int, value: int) -> None:
        await self._async_run_write(self.client.write_register, reg, value)

    async def async_write_registers(self, reg: int, values: list[int]) -> None:
        await self._async_run_write(self.client.write_registers, reg, values)

    async def async_update_bits(self, reg: int, set_bits: int, clear_bits: int) -> None:
        """Set/clear bits of a register, using the newest known value.

        Read and write happen together under the client's write lock, so two
        quick toggles of different bits can't overwrite each other.
        """
        def _update() -> None:
            with self.client.write_lock:
                current = int(self.client.registers.get(reg, 0))
                new = (current | set_bits) & ~clear_bits & 0xFFFF
                self.client.write_register(reg, new)

        await self._async_run_write(_update)

    async def async_run_once(self, minutes: int) -> None:
        """Start a one-shot run for ``minutes`` from the controller's current time."""
        minutes = max(1, int(minutes))

        def _trigger() -> None:
            regs = self.client.registers
            hour = int(regs.get(REG_CLOCK_HOUR, 0))
            minute = int(regs.get(REG_CLOCK_MIN, 0))
            start = hm_to_reg(hour, minute)
            total = hour * 60 + minute + minutes
            end = hm_to_reg((total // 60) % 24, total % 60)
            # the controller drops writes sent too fast; space them out
            for reg, val in (
                (REG_RUNONCE_START, start),
                (REG_RUNONCE_END, end),
                (REG_RUNONCE_ENABLE, 1),
            ):
                self.client.write_register(reg, val)
                time.sleep(1.8)

        await self._async_run_write(_trigger)
