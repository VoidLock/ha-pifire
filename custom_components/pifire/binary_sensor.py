"""PiFire binary sensor platform."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PiFire binary sensor entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info = data["device_info"]

    async_add_entities(
        [
            PiFirePowerRelaySensor(entry, coordinator, device_info),
            PiFireFanRelaySensor(entry, coordinator, device_info),
            PiFireAugerRelaySensor(entry, coordinator, device_info),
            PiFireIgniterRelaySensor(entry, coordinator, device_info),
        ]
    )


class PiFireOutputPinSensor(BinarySensorEntity):
    """Base class for PiFire output pin relay sensors."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        device_info: DeviceInfo,
        pin_name: str,
        friendly_name: str,
        icon_off: str,
        icon_on: str,
    ) -> None:
        """Initialize the output pin sensor."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._pin_name = pin_name
        self._attr_name = friendly_name
        self._attr_unique_id = f"{entry.entry_id}_{pin_name}_relay"
        self._icon_off = icon_off
        self._icon_on = icon_on

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the output pin is active."""
        data = self.coordinator.data or {}
        status = data.get("status", {})
        outpins = status.get("outpins", {})

        pin_state = outpins.get(self._pin_name)
        return bool(pin_state) if pin_state is not None else None

    @property
    def state(self) -> str | None:
        """Return the state of the binary sensor."""
        if self.is_on is None:
            return None
        return "On" if self.is_on else "Off"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return self._icon_on if self.is_on else self._icon_off

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


class PiFirePowerRelaySensor(PiFireOutputPinSensor):
    """Binary sensor for power relay status."""

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the power relay sensor."""
        super().__init__(
            entry,
            coordinator,
            device_info,
            "power",
            "Power Relay",
            "mdi:current-ac",
            "mdi:current-ac",
        )


class PiFireFanRelaySensor(PiFireOutputPinSensor):
    """Binary sensor for fan relay status."""

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the fan relay sensor."""
        super().__init__(
            entry,
            coordinator,
            device_info,
            "fan",
            "Fan Relay",
            "mdi:fan",
            "mdi:fan-alert",
        )


class PiFireAugerRelaySensor(PiFireOutputPinSensor):
    """Binary sensor for auger relay status."""

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the auger relay sensor."""
        super().__init__(
            entry,
            coordinator,
            device_info,
            "auger",
            "Auger Relay",
            "mdi:screw-machine-round-top",
            "mdi:screw-machine-round-top",
        )


class PiFireIgniterRelaySensor(PiFireOutputPinSensor):
    """Binary sensor for igniter relay status."""

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the igniter relay sensor."""
        super().__init__(
            entry,
            coordinator,
            device_info,
            "igniter",
            "Igniter Relay",
            "mdi:heating-coil",
            "mdi:heating-coil",
        )
