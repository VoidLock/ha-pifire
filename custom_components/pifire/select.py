"""PiFire select platform."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.components.select import SelectEntity
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
    """Set up PiFire select entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info = data["device_info"]

    async_add_entities(
        [
            PiFireModeSelector(entry, coordinator, device_info),
            PiFirePModeSelector(entry, coordinator, device_info),
        ]
    )


class PiFireModeSelector(SelectEntity):
    """Mode selector for PiFire."""

    _attr_has_entity_name = True
    _attr_name = "Mode"
    _attr_icon = "mdi:grill-outline"

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the Mode selector."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_options = [
            "Stop",
            "Startup",
            "Smoke",
            "Hold",
            "Shutdown",
            "Monitor",
        ]

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def current_option(self) -> str | None:
        """Return the current mode setting."""
        data = self.coordinator.data or {}
        status = data.get("status", {})

        mode = status.get("mode")
        if mode and mode.title() in self.options:
            return mode.title()

        # Fallback to Stop if mode not recognized
        return "Stop"

    async def async_select_option(self, option: str) -> None:
        """Set the mode."""
        if option not in self.options:
            raise HomeAssistantError(f"Invalid mode option: {option}")

        try:
            # Build URL from config entry data
            host = self._entry.data.get("host", "localhost")
            port = self._entry.data.get("port", 80)
            base_url = f"http://{host}:{port}"

            mode_lower = option.lower()

            # Special handling for Hold mode - needs temperature parameter
            if mode_lower == "hold":
                # Get current grill temperature or use a default
                data = self.coordinator.data or {}
                current = data.get("current", {})
                pmap = current.get("P", {})
                grill_temp = pmap.get("Grill", 225)  # Default to 225°F

                # Ensure temperature is within reasonable range
                if (
                    not isinstance(grill_temp, (int, float))
                    or grill_temp < 100
                    or grill_temp > 500
                ):
                    grill_temp = 225

                url = f"{base_url}/api/set/mode/hold/{int(grill_temp)}"
            else:
                url = f"{base_url}/api/set/mode/{mode_lower}"

            # Use Home Assistant's session
            session = async_get_clientsession(self.hass)

            async with session.post(url) as response:
                # Accept both 200 (OK) and 201 (Created) as success
                if response.status not in (200, 201):
                    response_text = await response.text()
                    raise HomeAssistantError(
                        f"API returned {response.status}: {response_text}"
                    )

            # Request immediate data refresh to update the selector
            await self.coordinator.async_request_refresh()

        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to set mode to %s: %s", option, err)
            raise HomeAssistantError(f"Failed to set mode: {err}") from err
        except Exception as err:
            _LOGGER.error("Failed to set mode to %s: %s", option, err)
            raise HomeAssistantError(f"Failed to set mode: {err}") from err

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        data = self.coordinator.data or {}
        status = data.get("status", {})

        attributes = {}

        # Add current mode
        mode = status.get("mode")
        if mode:
            attributes["raw_mode"] = mode

        # Add display mode if different
        display_mode = status.get("display_mode")
        if display_mode and display_mode != mode:
            attributes["display_mode"] = display_mode

        # Add status information
        if "status" in status:
            attributes["status_detail"] = status["status"]

        # Add current target temperature for hold mode
        current = data.get("current", {})
        pmap = current.get("P", {})
        grill_temp = pmap.get("Grill")
        if grill_temp is not None:
            attributes["target_temperature"] = grill_temp

        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


class PiFirePModeSelector(SelectEntity):
    """P-Mode selector for PiFire."""

    _attr_has_entity_name = True
    _attr_name = "P-Mode"
    _attr_icon = "mdi:cog-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the P-Mode selector."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_pmode"
        self._attr_options = [
            "P0",
            "P1",
            "P2",
            "P3",
            "P4",
            "P5",
            "P6",
            "P7",
            "P8",
            "P9",
        ]

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def current_option(self) -> str | None:
        """Return the current P-Mode setting."""
        data = self.coordinator.data or {}
        status = data.get("status", {})

        # Get current P-Mode from status
        pmode = status.get("pmode")
        if pmode is not None:
            try:
                pmode_num = int(pmode)
                if 0 <= pmode_num <= 9:
                    return f"P{pmode_num}"
            except (ValueError, TypeError):
                pass

        # Default fallback - check for last used or default to P1
        settings = status.get("settings", {})
        last_pmode = settings.get("last_pmode", 1)
        try:
            last_pmode_num = int(last_pmode)
            if 0 <= last_pmode_num <= 9:
                return f"P{last_pmode_num}"
        except (ValueError, TypeError):
            pass

        # Final fallback to P1
        return "P1"

    @property
    def available(self) -> bool:
        """Return True - P-Mode selector is always available."""
        return super().available

    def _is_pmode_active(self) -> bool:
        """Check if P-Mode switch is currently ON."""
        data = self.coordinator.data or {}
        status = data.get("status", {})

        # Check if currently in P-Mode (not Manual, Recipe, etc.)
        mode = status.get("mode", "").lower()
        return mode == "hold"

    async def async_select_option(self, option: str) -> None:
        """Set the P-Mode."""
        if option not in self.options:
            raise HomeAssistantError(f"Invalid P-Mode option: {option}")

        # Check if P-Mode switch is ON
        if not self._is_pmode_active():
            raise HomeAssistantError(
                "P-Mode must be active to change P-Mode settings. "
                "Please activate P-Mode first, then select the desired P-Mode level."
            )

        # Extract number from option (P0 -> 0, P1 -> 1, etc.)
        try:
            pmode_num = int(option[1])  # Get digit after 'P'
        except (ValueError, IndexError):
            raise HomeAssistantError(f"Invalid P-Mode format: {option}")

        try:
            # Build URL from config entry data
            host = self._entry.data.get("host", "localhost")
            port = self._entry.data.get("port", 80)
            base_url = f"http://{host}:{port}"

            url = f"{base_url}/api/set/pmode/{pmode_num}"

            # Use Home Assistant's session
            session = async_get_clientsession(self.hass)

            async with session.post(url) as response:
                # Accept both 200 (OK) and 201 (Created) as success
                if response.status not in (200, 201):
                    response_text = await response.text()
                    raise HomeAssistantError(
                        f"API returned {response.status}: {response_text}"
                    )

            # Request immediate data refresh to update the selector
            await self.coordinator.async_request_refresh()

        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to set P-Mode to %s: %s", option, err)
            raise HomeAssistantError(f"Failed to set P-Mode: {err}") from err
        except Exception as err:
            _LOGGER.error("Failed to set P-Mode to %s: %s", option, err)
            raise HomeAssistantError(f"Failed to set P-Mode: {err}") from err

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        data = self.coordinator.data or {}
        status = data.get("status", {})

        attributes = {}

        # Add current numeric P-Mode value
        pmode = status.get("pmode")
        if pmode is not None:
            attributes["pmode_number"] = pmode

        # Add P-Mode switch status
        attributes["pmode_active"] = self._is_pmode_active()

        # Add current mode
        mode = status.get("mode")
        if mode:
            attributes["current_mode"] = mode

        # Add any P-Mode related settings
        settings = status.get("settings", {})
        if "last_pmode" in settings:
            attributes["last_pmode"] = settings["last_pmode"]

        # Add P-Mode descriptions if available in status
        pmode_config = status.get("pmode_config", {})
        if pmode_config:
            attributes["pmode_config"] = pmode_config

        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()
