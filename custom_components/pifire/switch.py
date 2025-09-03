"""PiFire switch platform."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PiFire switch entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    device_info = data["device_info"]

    async_add_entities(
        [
            PiFirePModeSwitch(entry, coordinator, client, device_info),
            PiFireSmokePlusSwitch(entry, coordinator, client, device_info),
        ]
    )


class PiFirePModeSwitch(SwitchEntity):
    """Switch entity for enabling/disabling P-Mode."""

    _attr_has_entity_name = True
    _attr_name = "P-Mode Enable"
    _attr_icon = "mdi:tune"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the P-Mode switch."""
        self._entry = entry
        self.coordinator = coordinator
        self.client = client
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_p_mode_switch"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if P-Mode is enabled."""
        data = self.coordinator.data or {}
        status = data.get("status") or {}
        # P-Mode is enabled when p_mode is not 0
        p_mode = status.get("p_mode", 0)
        try:
            return int(p_mode) != 0
        except (TypeError, ValueError):
            return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on P-Mode (set to P-1 by default)."""
        try:
            await self.client.set_p_mode(1)
            _LOGGER.debug("Successfully enabled P-Mode")
            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable P-Mode: %s", err)
            raise HomeAssistantError("Failed to enable P-Mode") from err

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off P-Mode (set to P-0)."""
        try:
            await self.client.set_p_mode(0)
            _LOGGER.debug("Successfully disabled P-Mode")
            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable P-Mode: %s", err)
            raise HomeAssistantError("Failed to disable P-Mode") from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


class PiFireSmokePlusSwitch(SwitchEntity):
    """Switch entity for enabling/disabling Smoke Plus mode."""

    _attr_has_entity_name = True
    _attr_name = "Smoke Plus"
    _attr_icon = "mdi:fan"

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the Smoke Plus switch."""
        self._entry = entry
        self.coordinator = coordinator
        self.client = client
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_smoke_plus_switch"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if Smoke Plus is enabled."""
        data = self.coordinator.data or {}
        status = data.get("status") or {}
        # Check if s_plus is enabled
        s_plus = status.get("s_plus", False)
        return bool(s_plus) if s_plus is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on Smoke Plus mode."""
        try:
            # Use direct API call with correct endpoint
            host = self._entry.data.get("host", "localhost")
            port = self._entry.data.get("port", 80)
            base_url = f"http://{host}:{port}"
            url = f"{base_url}/api/set/splus/true"

            session = async_get_clientsession(self.hass)
            async with session.post(url) as response:
                if response.status not in (200, 201):
                    response_text = await response.text()
                    raise HomeAssistantError(
                        f"API returned {response.status}: {response_text}"
                    )

            _LOGGER.debug("Successfully enabled Smoke Plus")
            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to enable Smoke Plus: %s", err)
            raise HomeAssistantError("Failed to enable Smoke Plus") from err
        except Exception as err:
            _LOGGER.error("Failed to enable Smoke Plus: %s", err)
            raise HomeAssistantError("Failed to enable Smoke Plus") from err

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off Smoke Plus mode."""
        try:
            # Use direct API call with correct endpoint
            host = self._entry.data.get("host", "localhost")
            port = self._entry.data.get("port", 80)
            base_url = f"http://{host}:{port}"
            url = f"{base_url}/api/set/splus/false"

            session = async_get_clientsession(self.hass)
            async with session.post(url) as response:
                if response.status not in (200, 201):
                    response_text = await response.text()
                    raise HomeAssistantError(
                        f"API returned {response.status}: {response_text}"
                    )

            _LOGGER.debug("Successfully disabled Smoke Plus")
            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to disable Smoke Plus: %s", err)
            raise HomeAssistantError("Failed to disable Smoke Plus") from err
        except Exception as err:
            _LOGGER.error("Failed to disable Smoke Plus: %s", err)
            raise HomeAssistantError("Failed to disable Smoke Plus") from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()
