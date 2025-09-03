from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CLIENT,
    COORDINATOR,
    PLATFORMS,
    DEFAULT_UPDATE_SECONDS,
)
from .pifire_client import PiFireClient, PiFireError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    base_url: str = entry.data.get(CONF_BASE_URL, "http://pifire.local:8080").rstrip("/")
    client = PiFireClient(hass, base_url)

    async def _update():
        try:
            return await client.get_current()
        except (Exception, PiFireError) as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="pifire_coordinator",
        update_method=_update,
        update_interval=timedelta(seconds=DEFAULT_UPDATE_SECONDS),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {CLIENT: client, COORDINATOR: coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
