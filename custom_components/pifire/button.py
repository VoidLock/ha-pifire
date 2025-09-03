"""PiFire button platform."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map display names to API values for prime next mode
DISPLAY_TO_API = {
    "Stop": "stop",
    "Startup": "startup",
    "Smoke": "smoke",
    "Hold": "hold",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PiFire button entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    device_info = data["device_info"]

    async_add_entities(
        [
            PiFireRestartButton(entry, coordinator, client, device_info),
            PiFireRebootButton(entry, coordinator, client, device_info),
            PiFireShutdownButton(entry, coordinator, client, device_info),
            PiFirePrimePelletsButton(entry, coordinator, client, device_info),
        ]
    )


class PiFireSystemButton(ButtonEntity):
    """Base class for PiFire system control buttons."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        client,
        device_info: DeviceInfo,
        name: str,
        endpoint: str,
    ) -> None:
        """Initialize the button."""
        self._entry = entry
        self.coordinator = coordinator
        self.client = client
        self._attr_device_info = device_info
        self._attr_name = name
        self._endpoint = endpoint
        self._attr_unique_id = f"{entry.entry_id}_{name.lower().replace(' ', '_')}"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            # Use direct API call with correct endpoint
            host = self._entry.data.get("host", "localhost")
            port = self._entry.data.get("port", 80)
            base_url = f"http://{host}:{port}"
            url = f"{base_url}{self._endpoint}"

            session = async_get_clientsession(self.hass)
            async with session.post(url) as response:
                if response.status not in (200, 201):
                    response_text = await response.text()
                    raise HomeAssistantError(
                        f"API returned {response.status}: {response_text}"
                    )

            _LOGGER.info("Successfully executed %s command", self._attr_name)
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to execute %s command: %s", self._attr_name, err)
            raise HomeAssistantError(
                f"Failed to execute {self._attr_name} command"
            ) from err
        except Exception as err:
            _LOGGER.error("Failed to execute %s command: %s", self._attr_name, err)
            raise HomeAssistantError(
                f"Failed to execute {self._attr_name} command"
            ) from err


class PiFireRestartButton(PiFireSystemButton):
    """Button to restart PiFire application."""

    _attr_icon = "mdi:restart"

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the restart button."""
        super().__init__(
            entry,
            coordinator,
            client,
            device_info,
            "Restart PiFire",
            "/api/cmd/restart",
        )


class PiFireRebootButton(PiFireSystemButton):
    """Button to reboot PiFire device."""

    _attr_icon = "mdi:restart-alert"

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the reboot button."""
        super().__init__(
            entry, coordinator, client, device_info, "Reboot Device", "/api/cmd/reboot"
        )


class PiFireShutdownButton(PiFireSystemButton):
    """Button to shutdown PiFire system."""

    _attr_icon = "mdi:power"

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the shutdown button."""
        super().__init__(
            entry,
            coordinator,
            client,
            device_info,
            "Shutdown System",
            "/api/cmd/shutdown",
        )


class PiFirePrimePelletsButton(ButtonEntity):
    """Button to prime pellets."""

    _attr_has_entity_name = True
    _attr_name = "Prime Pellets"
    _attr_icon = "mdi:grain"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the prime pellets button."""
        self._entry = entry
        self.coordinator = coordinator
        self.client = client
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_prime_pellets"

    async def async_press(self) -> None:
        """Handle the prime pellets button press."""
        try:
            # Get the grams value from the number entity
            entity_registry = async_get(self.hass)
            grams_entity_id = "number.pifire_prime_pellets_grams"

            # Try to get the entity state
            grams_state = self.hass.states.get(grams_entity_id)
            if grams_state and grams_state.state not in ("unknown", "unavailable"):
                try:
                    grams = int(float(grams_state.state))
                except (ValueError, TypeError):
                    grams = 100  # Default fallback
            else:
                grams = 100  # Default fallback

            # Get the current mode from the mode selector for next_mode
            mode_entity_id = "select.pifire_mode"
            mode_state = self.hass.states.get(mode_entity_id)
            if mode_state and mode_state.state not in ("unknown", "unavailable"):
                display_mode = mode_state.state
                next_mode = DISPLAY_TO_API.get(display_mode, "stop")
            else:
                next_mode = "stop"  # Default fallback

            await self.client.prime_pellets(grams, next_mode)
            _LOGGER.info(
                "Successfully started pellet priming: %s grams, next mode: %s",
                grams,
                next_mode,
            )

            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to prime pellets: %s", err)
            raise HomeAssistantError("Failed to prime pellets") from err
