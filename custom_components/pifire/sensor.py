from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, COORDINATOR

TEMP_KEY_REGEX = re.compile(r"(temp|temperature)$", re.IGNORECASE)
PERCENT_KEY_REGEX = re.compile(r"(level|percent|percentage)$", re.IGNORECASE)

# Friendly name overrides for common PiFire keys
FRIENDLY = {
    "Grill temp": "Grill Temperature",
    "Probe1 temp": "Probe 1 Temperature",
    "Probe2 temp": "Probe 2 Temperature",
    "Pelletlevel": "Pellet Level",
    "Mode": "Mode",
    "Status": "Status",
    "Units": "Units",
    "Pellets": "Pellet Type",
}

# Keys to skip (internal / noisy)
SKIP_KEYS = {"@odata.context"}  # keep list if you find junk fields


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[COORDINATOR]

    manager = _DynamicSensorManager(hass, entry, coordinator, async_add_entities)
    # Create initial entities from the first payload
    manager.discover_from_payload(coordinator.data)

    # Listen for future updates adding *new* entities if PiFire starts reporting more
    @callback
    def _maybe_discover_new():
        manager.discover_from_payload(coordinator.data)

    coordinator.async_add_listener(_maybe_discover_new)


class _DynamicSensorManager:
    """Tracks which keys we've already created entities for; adds new ones as they appear."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, async_add_entities: AddEntitiesCallback):
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.async_add_entities = async_add_entities
        self._created_keys: Set[str] = set()

    def discover_from_payload(self, payload: Dict[str, Any] | None) -> None:
        if not isinstance(payload, dict):
            return

        new_entities: List[SensorEntity] = []

        # Determine units (°F/°C) once per payload for temp sensors
        units = str(payload.get("Units") or payload.get("units") or "").upper()
        temp_unit = "°C" if units == "C" else "°F"

        for raw_key, value in payload.items():
            if raw_key in SKIP_KEYS:
                continue
            key = str(raw_key)

            # Already have an entity for this key → skip
            if key in self._created_keys:
                continue

            # Decide if/what kind of sensor to create
            ent = self._build_entity_for_key(key, value, temp_unit)
            if ent:
                self._created_keys.add(key)
                new_entities.append(ent)

        if new_entities:
            self.async_add_entities(new_entities)

    def _build_entity_for_key(self, key: str, value: Any, temp_unit: str) -> Optional[SensorEntity]:
        # Try special cases first (known PiFire fields)
        nice_name = FRIENDLY.get(key)

        # Temperature-like?
        if self._looks_like_temperature(key, value):
            name = nice_name or self._titleize_key(key)
            return PiFireDynamicSensor(
                coordinator=self.coordinator,
                entry=self.entry,
                source_key=key,
                name=name,
                unit=temp_unit,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                value_transform=_to_float_safe,
            )

        # Percentage-like (pellet level etc.)
        if self._looks_like_percent(key, value):
            name = nice_name or self._titleize_key(key)
            return PiFireDynamicSensor(
                coordinator=self.coordinator,
                entry=self.entry,
                source_key=key,
                name=name,
                unit="%",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                value_transform=_to_float_safe,
            )

        # Strings / enums we care about (Mode, Status, Units, Pellets)
        if isinstance(value, (str, bool, int, float)):
            if key.lower() in ("mode", "status", "units", "pellets"):
                name = nice_name or self._titleize_key(key)
                return PiFireDynamicSensor(
                    coordinator=self.coordinator,
                    entry=self.entry,
                    source_key=key,
                    name=name,
                    unit=None,
                    device_class=None,
                    state_class=None,
                    value_transform=_identity,
                )

        # Otherwise, ignore unknown noisy keys
        return None

    @staticmethod
    def _looks_like_temperature(key: str, value: Any) -> bool:
        if isinstance(value, (int, float)):
            # typical grill temps
            if -40 <= float(value) <= 1000:
                if TEMP_KEY_REGEX.search(key.replace(" ", "_")):
                    return True
        # Also match common PiFire names exactly even if value looks odd
        return key in ("Grill temp", "Probe1 temp", "Probe2 temp")

    @staticmethod
    def _looks_like_percent(key: str, value: Any) -> bool:
        if isinstance(value, (int, float)):
            if 0 <= float(value) <= 100:
                if PERCENT_KEY_REGEX.search(key.replace(" ", "_")):
                    return True
        # Exact known pellet level key
        return key == "Pelletlevel"

    @staticmethod
    def _titleize_key(key: str) -> str:
        # "Probe1 temp" -> "Probe1 Temp"; "pellet_level" -> "Pellet Level"
        s = key.replace("_", " ").strip()
        return " ".join(w[:1].upper() + w[1:] for w in s.split(" "))


class PiFireDynamicSensor(CoordinatorEntity, SensorEntity):
    """A generic sensor backed by a key from /api/current."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:grill"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        source_key: str,
        name: str,
        unit: Optional[str],
        device_class,
        state_class,
        value_transform,
    ):
        super().__init__(coordinator)
        self._entry = entry
        self._key = source_key
        self._attr_name = f"PiFire {name}"
        self._attr_unique_id = f"{entry.entry_id}_dyn_{_normalize_uid(source_key)}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._transform = value_transform

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        val = data.get(self._key)
        return self._transform(val)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "PiFire",
            "manufacturer": "PiFire",
            "model": "Grill Controller",
        }


def _normalize_uid(key: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", key.lower().replace(" ", "_"))


def _to_float_safe(val: Any) -> Any:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return val


def _identity(val: Any) -> Any:
    return val
