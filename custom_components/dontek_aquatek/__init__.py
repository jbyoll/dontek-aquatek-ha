"""The Dontek Aquatek pool controller integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_MAC, DOMAIN
from .coordinator import DontekCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
    Platform.BUTTON,
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dontek Aquatek from a config entry."""
    mac = entry.data[CONF_MAC]
    coordinator = DontekCoordinator(hass, entry, mac)
    try:
        await coordinator.async_connect()
    except Exception as err:  # noqa: BLE001 - e.g. no internet at boot
        # HA retries setup later instead of leaving the integration dead
        await hass.async_add_executor_job(coordinator.client.disconnect)
        raise ConfigEntryNotReady(f"Cannot reach the Dontek cloud: {err}") from err
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: DontekCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
