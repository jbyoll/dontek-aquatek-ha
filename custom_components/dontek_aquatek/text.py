"""Text entities for Dontek Aquatek (socket names)."""
from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SOCKET_COUNT,
    SOCKET_NAME_MAX_LEN,
    encode_name,
    socket_name,
    socket_name_reg,
)
from .coordinator import DontekCoordinator
from .entity import DontekEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DontekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SocketNameText(coordinator, socket) for socket in range(1, SOCKET_COUNT + 1)
    )


class SocketNameText(DontekEntity, TextEntity):
    """The name a socket shows in the app (8 registers from 57344 + 8 * (n - 1)).

    Same write as the app's Appliance Setup rename: all 8 registers in one
    message, zero padded. Clear the text to remove the name.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = SOCKET_NAME_MAX_LEN
    _attr_pattern = r"^[ -~]*$"  # printable ASCII, like the app

    def __init__(self, coordinator: DontekCoordinator, socket: int) -> None:
        super().__init__(coordinator)
        self._socket = socket
        self._attr_name = f"Socket {socket} name"
        self._attr_unique_id = f"{coordinator.mac}_socket{socket}_name"

    @property
    def native_value(self) -> str | None:
        if self.reg(socket_name_reg(self._socket)) is None:
            return None
        return socket_name(self.coordinator.data or {}, self._socket)

    async def async_set_value(self, value: str) -> None:
        value = value.strip()
        try:
            values = encode_name(value)
        except UnicodeEncodeError as err:
            raise HomeAssistantError(
                "Socket names can only use plain letters, numbers and symbols"
            ) from err
        await self.coordinator.async_write_registers(socket_name_reg(self._socket), values)
