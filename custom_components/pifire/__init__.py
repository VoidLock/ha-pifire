"""PiFire integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PLATFORMS, CONF_HOST
from .pifire_client import PiFireClient

_LOGGER = logging.getLogger(__name__)

# Define update intervals
FAST_UPDATE_INTERVAL = timedelta(seconds=5)
SLOW_UPDATE_INTERVAL = timedelta(seconds=30)

# Modes that require fast updates
FAST_UPDATE_MODES = {"startup", "smoke", "monitor", "hold"}


class PiFireDataUpdateCoordinator(DataUpdateCoordinator):
    """Custom coordinator with dynamic update intervals based on PiFire mode."""

    def __init__(self, hass: HomeAssistant, client: PiFireClient, entry: ConfigEntry):
        """Initialize the coordinator."""
        self.client = client
        self._entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name="pifire",
            update_method=self._async_update_data,
            update_interval=SLOW_UPDATE_INTERVAL,  # Start with slow interval
            config_entry=entry,
        )

    async def _async_update_data(self):
        """Update coordinator data and adjust update interval based on mode."""
        try:
            # Get both current status and hopper data
            current_data = await self.client.get_current()
            hopper_data = await self.client.get_hopper_data()

            # Combine the data
            combined_data = current_data.copy()
            if hopper_data:
                combined_data["hopper"] = hopper_data

            # Check current mode and adjust update interval
            self._adjust_update_interval(combined_data)

            return combined_data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _adjust_update_interval(self, data: dict) -> None:
        """Adjust update interval based on current PiFire mode."""
        try:
            status = data.get("status", {})
            current_mode = status.get("mode", "").lower()

            # Determine required update interval
            if current_mode in FAST_UPDATE_MODES:
                required_interval = FAST_UPDATE_INTERVAL
            else:
                required_interval = SLOW_UPDATE_INTERVAL

            # Only change if different from current interval
            if self.update_interval != required_interval:
                _LOGGER.debug(
                    "Changing update interval from %s to %s (mode: %s)",
                    self.update_interval,
                    required_interval,
                    current_mode,
                )
                self.update_interval = required_interval

        except Exception as err:
            _LOGGER.warning("Failed to adjust update interval: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PiFire from a config entry."""
    host = entry.data[CONF_HOST]
    client = PiFireClient(hass, host)

    # Create custom coordinator with dynamic update intervals
    coordinator = PiFireDataUpdateCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    # Create device info with configuration URL
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="PiFire",
        manufacturer="PiFire",
        model="Grill Controller",
        configuration_url=f"http://{host}",
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "device_info": device_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
