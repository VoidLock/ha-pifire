from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up PiFire sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    base_url = data.get("base_url")  # Not used yet, but here for later steps.

    # Create one "hello world" sensor so we can see the integration works.
    async_add_entities([PiFireHelloSensor(entry, base_url)], update_before_add=False)


class PiFireHelloSensor(SensorEntity):
    """A simple hello-world sensor to prove the plumbing works."""

    _attr_has_entity_name = True
    _attr_name = "Hello Status"
    _attr_icon = "mdi:grill"

    def __init__(self, entry: ConfigEntry, base_url: str | None):
        self._entry = entry
        self._base_url = base_url or ""
        self._attr_unique_id = f"{entry.entry_id}_hello"

    @property
    def native_value(self):
        # For the first step, we just report "ready".
        return "ready"

    @property
    def device_info(self):
        # Makes a nice device card in HA's UI with your integration name.
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "PiFire",
            "manufacturer": "PiFire",
            "model": "Grill Controller",
            "configuration_url": self._base_url or None,
        }
