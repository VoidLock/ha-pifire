"""PiFire sensor platform."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PiFire sensors from live payload."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info = data["device_info"]

    mgr = _SensorManager(hass, entry, coordinator, device_info, async_add_entities)
    # First discovery: this should create any available sensors
    mgr.discover_from_payload(coordinator.data)

    @callback
    def _on_update() -> None:
        mgr.discover_from_payload(coordinator.data)

    coordinator.async_add_listener(_on_update)


class _SensorManager:
    """Creates sensors for enabled probes; adds new ones as they appear."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator,
        device_info: DeviceInfo,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.device_info = device_info
        self.async_add_entities = async_add_entities
        self._created: set[str] = set()

    def discover_from_payload(self, payload: dict[str, Any] | None) -> None:
        """Discover sensors from payload data."""
        if not isinstance(payload, dict):
            return

        status = payload.get("status") or {}
        current = payload.get("current") or {}
        ftemps: dict[str, Any] = current.get("F") or {}
        nt: dict[str, Any] = current.get("NT") or {}
        pmap: dict[str, Any] = current.get("P") or {}
        hopper = payload.get("hopper") or {}

        # ---- Recipe Sensor ----
        if "recipe" not in self._created:
            try:
                self.async_add_entities(
                    [PiFireRecipeSensor(self.entry, self.coordinator, self.device_info)]
                )
                self._created.add("recipe")
                _LOGGER.debug("PiFire: created Recipe sensor")
            except Exception:
                _LOGGER.exception("PiFire: failed to create Recipe sensor")

        # ---- Runtime Sensor ----
        if "runtime" not in self._created:
            try:
                self.async_add_entities(
                    [
                        PiFireRuntimeSensor(
                            self.entry, self.coordinator, self.device_info
                        )
                    ]
                )
                self._created.add("runtime")
                _LOGGER.debug("PiFire: created Runtime sensor")
            except Exception:
                _LOGGER.exception("PiFire: failed to create Runtime sensor")

        # ---- Pellet Level Sensor (if hopper data available) ----
        if (
            isinstance(hopper, dict)
            and "hopper_level" in hopper
            and "pellet_level" not in self._created
        ):
            try:
                self.async_add_entities(
                    [
                        PiFirePelletLevelSensor(
                            self.entry, self.coordinator, self.device_info
                        )
                    ]
                )
                self._created.add("pellet_level")
                _LOGGER.debug("PiFire: created Pellet Level sensor")
            except Exception:
                _LOGGER.exception("PiFire: failed to create Pellet Level sensor")

        # ---- Enabled probes → temperature sensors ----
        enabled_labels: list[str] = []

        probe_status = status.get("probe_status") or {}
        for group_key in ("P", "F", "AUX"):
            group = probe_status.get(group_key) or {}
            if isinstance(group, dict):
                for label, meta in group.items():
                    if isinstance(meta, dict) and meta.get("enabled", False):
                        enabled_labels.append(str(label))

        # Fallback: if probe_status missing or empty, use whatever appears in F/NT/P
        if not enabled_labels:
            enabled_labels = sorted(
                set(list(ftemps.keys()) + list(nt.keys()) + list(pmap.keys()))
            )

        # Ensure Grill appears first if enabled for nicer UI ordering
        enabled_labels_sorted = sorted(
            enabled_labels, key=lambda x: (x.lower() != "grill", x)
        )

        new_entities: list[SensorEntity] = []
        for label in enabled_labels_sorted:
            # Only add if a value exists somewhere
            exists = (label in ftemps) or (label in nt) or (label in pmap)
            if not exists:
                continue

            key = f"probe:{label}"
            if key in self._created:
                continue

            try:
                new_entities.append(
                    PiFireProbeTempSensor(
                        entry=self.entry,
                        coordinator=self.coordinator,
                        device_info=self.device_info,
                        label=label,
                        friendly_name=_pretty_probe_name(label),
                    )
                )
                self._created.add(key)
                _LOGGER.debug("PiFire: created probe sensor for label '%s'", label)
            except Exception:
                _LOGGER.exception(
                    "PiFire: failed to create probe sensor for '%s'", label
                )

        if new_entities:
            self.async_add_entities(new_entities)


class PiFireRecipeSensor(SensorEntity):
    """Boolean sensor showing if a recipe is currently active."""

    _attr_has_entity_name = True
    _attr_name = "Recipe"
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the recipe sensor."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_recipe"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def native_value(self) -> bool:
        """Return True if a recipe is currently active."""
        data = self.coordinator.data or {}
        status = data.get("status") or {}

        # Check the mode to determine if a recipe is active
        mode = status.get("mode", "").lower()
        return mode == "recipe"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        data = self.coordinator.data or {}
        status = data.get("status") or {}

        attributes = {}

        # Add mode information
        mode = status.get("mode")
        if mode:
            attributes["mode"] = mode

        # Add display mode if different from mode
        display_mode = status.get("display_mode")
        if display_mode and display_mode != mode:
            attributes["display_mode"] = display_mode

        # Add recipe name if available
        recipe_name = status.get("name", "").strip()
        if recipe_name:
            attributes["recipe_name"] = recipe_name

        # Add startup/shutdown durations if in recipe mode
        if status.get("mode", "").lower() == "recipe":
            if "start_duration" in status:
                attributes["start_duration"] = status["start_duration"]
            if "shutdown_duration" in status:
                attributes["shutdown_duration"] = status["shutdown_duration"]
            if "start_time" in status:
                attributes["start_time"] = status["start_time"]

        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


class PiFireRuntimeSensor(SensorEntity):
    """Sensor showing how long PiFire has been running since startup."""

    _attr_has_entity_name = True
    _attr_name = "Runtime"
    _attr_icon = "mdi:timer-outline"

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the runtime sensor."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_runtime"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False

        # Only available when in runtime-tracking modes
        data = self.coordinator.data or {}
        status = data.get("status", {})
        mode = status.get("mode", "").lower()
        return mode in {"smoke", "hold", "monitor", "startup", "shutdown"}

    @property
    def native_value(self) -> str | None:
        """Return the runtime in HH:MM:SS format."""
        # Return None if not available (not in runtime-tracking modes)
        if not self.available:
            return None

        data = self.coordinator.data or {}
        status = data.get("status", {})

        # Get start_time timestamp
        start_time = status.get("start_time")
        if start_time is None:
            return "00:00:00"

        try:
            # Convert start_time epoch timestamp to datetime
            start_datetime = datetime.fromtimestamp(float(start_time), tz=timezone.utc)

            # Calculate runtime in seconds
            now = dt_util.utcnow()
            runtime_delta = now - start_datetime
            total_seconds = int(runtime_delta.total_seconds())

            # Ensure non-negative runtime
            if total_seconds < 0:
                total_seconds = 0

            # Format as HH:MM:SS
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except (TypeError, ValueError, OSError):
            return "00:00:00"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        # Return empty attributes if not available (not in runtime-tracking modes)
        if not self.available:
            return None

        data = self.coordinator.data or {}
        status = data.get("status", {})

        attributes = {}

        # Add current mode for reference
        mode = status.get("mode")
        if mode:
            attributes["mode"] = mode

        # Add start_time timestamp as attribute
        start_time = status.get("start_time")
        if start_time:
            try:
                start_datetime = datetime.fromtimestamp(
                    float(start_time), tz=timezone.utc
                )
                attributes["start_time"] = start_datetime.isoformat()
                attributes["start_time_epoch"] = float(start_time)
            except (TypeError, ValueError, OSError):
                attributes["start_time_epoch"] = start_time

        # Add total runtime in seconds for reference
        if start_time:
            try:
                start_datetime = datetime.fromtimestamp(
                    float(start_time), tz=timezone.utc
                )
                now = dt_util.utcnow()
                runtime_delta = now - start_datetime
                total_seconds = max(0, int(runtime_delta.total_seconds()))
                attributes["total_seconds"] = total_seconds
            except (TypeError, ValueError, OSError):
                pass

        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


class PiFireOutputPinSensor(SensorEntity):
    """Boolean sensor showing output pin relay state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        device_info: DeviceInfo,
        pin_key: str,
        name: str,
        icon: str,
        diagnostic: bool = False,
    ) -> None:
        """Initialize the output pin sensor."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._pin_key = pin_key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{pin_key}_relay"

        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def native_value(self) -> bool | None:
        """Return the output pin state."""
        data = self.coordinator.data or {}
        status = data.get("status") or {}
        outpins = status.get("outpins") or {}

        pin_state = outpins.get(self._pin_key)
        return bool(pin_state) if pin_state is not None else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


class PiFirePelletLevelSensor(SensorEntity):
    """Sensor showing pellet level percentage."""

    _attr_has_entity_name = True
    _attr_name = "Pellet Level"
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, entry: ConfigEntry, coordinator, device_info: DeviceInfo
    ) -> None:
        """Initialize the pellet level sensor."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_pellet_level"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def native_value(self) -> int | None:
        """Return the pellet level percentage."""
        data = self.coordinator.data or {}
        hopper = data.get("hopper") or {}
        level = hopper.get("hopper_level")

        try:
            return int(level) if level is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        data = self.coordinator.data or {}
        hopper = data.get("hopper") or {}
        pellets = hopper.get("hopper_pellets")

        attributes = {}
        if pellets:
            attributes["pellet_type"] = pellets

        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


class PiFireProbeTempSensor(SensorEntity):
    """Temperature sensor for a probe label."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        device_info: DeviceInfo,
        label: str,
        friendly_name: str,
    ) -> None:
        """Initialize the probe temperature sensor."""
        self._entry = entry
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self._label = label
        self._attr_name = friendly_name
        self._attr_unique_id = f"{entry.entry_id}_temp_{_slugify(label)}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        units = str(
            ((self.coordinator.data or {}).get("status") or {}).get("units") or ""
        ).upper()
        return "°C" if units == "C" else "°F"

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        data = self.coordinator.data or {}
        status = data.get("status") or {}
        cur = data.get("current") or {}
        ftemps: dict[str, Any] = cur.get("F") or {}
        nt: dict[str, Any] = cur.get("NT") or {}
        pmap: dict[str, Any] = cur.get("P") or {}

        # Check mode - if "Stop", return 0 for Grill temperature
        mode = status.get("mode", "").lower()
        if self._label.lower() == "grill" and mode == "stop":
            return 0.0

        def _num(x: Any) -> float | None:
            try:
                # Handle "Unknown" string values
                if isinstance(x, str) and x.lower() == "unknown":
                    return 0.0
                return float(x)
            except (TypeError, ValueError):
                return None

        label = self._label

        # For Grill temperature, use P["Grill"] value specifically
        if label.lower() == "grill":
            grill_temp = _num(pmap.get("Grill"))
            return grill_temp

        # For other probes, use F[label] first, then NT[label] as fallback
        val = _num(ftemps.get(label))
        if val is None or val == 0:
            alt = _num(nt.get(label))
            val = alt if alt not in (None, 0) else val

        return val

    @property
    def icon(self) -> str:
        """Return the icon based on probe type."""
        # Special case for grill
        if self._label.lower() == "grill":
            return "mdi:grill"

        # Check if this probe is a Bluetooth thermostat
        data = self.coordinator.data or {}
        thermostats = data.get("thermostats", {})

        # Look for this probe label in thermostats data
        for thermostat_id, thermostat_data in thermostats.items():
            if isinstance(thermostat_data, dict):
                # Check if this thermostat corresponds to our probe label
                thermostat_label = thermostat_data.get("label", "")
                if thermostat_label == self._label:
                    # Found matching thermostat - check if it's Bluetooth
                    connection_type = thermostat_data.get("type", "").lower()
                    if "bluetooth" in connection_type or "bt" in connection_type:
                        return "mdi:thermometer-bluetooth"

        # Default thermometer icon for non-Bluetooth probes
        return "mdi:thermometer"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes with probe metadata."""
        data = self.coordinator.data or {}
        status = data.get("status") or {}
        probe_status = status.get("probe_status") or {}

        attributes = {}

        # Find probe metadata in probe_status
        probe_meta = None
        for group_key in ("P", "F", "AUX"):
            group = probe_status.get(group_key) or {}
            if isinstance(group, dict) and self._label in group:
                probe_meta = group[self._label]
                break

        if probe_meta and isinstance(probe_meta, dict):
            # Device information
            device = probe_meta.get("device")
            if device:
                attributes["device"] = device

            # Probe type (Primary/Food/etc)
            probe_type = probe_meta.get("type")
            if probe_type:
                attributes["type"] = probe_type

            # Port information
            port = probe_meta.get("port")
            if port:
                attributes["port"] = port

            # Enabled status
            enabled = probe_meta.get("enabled")
            if enabled is not None:
                attributes["enabled"] = enabled

            # Custom name (if different from label)
            name = probe_meta.get("name")
            if name and name != self._label:
                attributes["custom_name"] = name

            # Configuration details
            config = probe_meta.get("config")
            if config and isinstance(config, dict):
                # Hardware configuration
                if "i2c_bus_addr" in config:
                    attributes["i2c_address"] = config["i2c_bus_addr"]
                if "voltage_ref" in config:
                    attributes["voltage_reference"] = config["voltage_ref"]
                if "transient" in config:
                    attributes["transient"] = config["transient"]
                if "hardware_id" in config:
                    attributes["hardware_id"] = config["hardware_id"]

                # ADC resistance values
                adc_values = {}
                for key, value in config.items():
                    if key.startswith("ADC") and key.endswith("_rd"):
                        adc_num = key.replace("ADC", "").replace("_rd", "")
                        adc_values[f"adc_{adc_num}_resistance"] = value
                if adc_values:
                    attributes.update(adc_values)

            # Profile/calibration information
            profile = probe_meta.get("profile")
            if profile and isinstance(profile, dict):
                profile_id = profile.get("id")
                if profile_id:
                    attributes["profile_id"] = profile_id

                profile_name = profile.get("name")
                if profile_name:
                    attributes["profile_name"] = profile_name

                # Calibration coefficients
                for coeff in ("A", "B", "C"):
                    if coeff in profile:
                        attributes[f"coefficient_{coeff.lower()}"] = profile[coeff]

            # Status information
            status_info = probe_meta.get("status")
            if status_info and isinstance(status_info, dict):
                # Connection status for Bluetooth probes
                if "connected" in status_info:
                    attributes["connected"] = status_info["connected"]
                if "disabled" in status_info:
                    attributes["disabled"] = status_info["disabled"]

                # Error information
                error = status_info.get("error")
                if error is not None:
                    attributes["error"] = error

        # Add current temperature values from other sources for comparison
        current = data.get("current") or {}
        ftemps = current.get("F") or {}
        nt = current.get("NT") or {}

        if self._label in ftemps:
            attributes["f_temp"] = ftemps[self._label]
        if self._label in nt:
            attributes["nt_temp"] = nt[self._label]

        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


def _pretty_probe_name(label: str) -> str:
    """Turn 'Probe1' -> 'Probe 1 Temperature', 'Grill' -> 'Grill Temperature'."""
    if label.lower() == "grill":
        return "Grill Temperature"

    spaced = re.sub(r"(?<=\D)(\d+)$", r" \1", label)
    return f"{spaced} Temperature"


def _slugify(s: str) -> str:
    """Convert string to slug format."""
    return re.sub(r"[^a-z0-9_]+", "", s.lower().replace(" ", "_"))
