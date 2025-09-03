"""PiFire number platform."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PiFire number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    device_info = data["device_info"]

    async_add_entities(
        [
            PiFireTemperatureSetpoint(entry, coordinator, client, device_info),
            PiFirePrimePelletsGrams(entry, coordinator, client, device_info),
        ]
    )


class PiFireTemperatureSetpoint(NumberEntity):
    """Number entity for controlling PiFire temperature setpoint."""

    _attr_has_entity_name = True
    _attr_name = "Temperature Setpoint"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_mode = NumberMode.BOX
    _attr_step = 1
    _attr_icon = "mdi:thermostat"

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the temperature setpoint number entity."""
        self._entry = entry
        self.coordinator = coordinator
        self.client = client
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_temperature_setpoint"
        self._last_set_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

        # Initialize with current setpoint from coordinator
        if self.coordinator.data:
            self._initialize_from_coordinator()

    def _get_current_psp(self) -> float | None:
        """Get the current PSP (Primary Setpoint) value from coordinator data."""
        data = self.coordinator.data or {}
        current = data.get("current", {})

        # Try PSP first (Primary Setpoint)
        psp = current.get("PSP")
        if psp is not None:
            try:
                return float(psp)
            except (TypeError, ValueError):
                pass

        # Fallback to P.Grill if PSP not available
        pmap = current.get("P", {})
        setpoint = pmap.get("Grill")
        if setpoint is not None:
            try:
                return float(setpoint)
            except (TypeError, ValueError):
                pass

        return None

    def _initialize_from_coordinator(self) -> None:
        """Initialize the setpoint value from coordinator data."""
        current_psp = self._get_current_psp()
        if current_psp is not None:
            self._last_set_value = current_psp

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False

        # Only available when in hold mode
        data = self.coordinator.data or {}
        status = data.get("status", {})
        mode = status.get("mode", "").lower()
        return mode == "hold"

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        data = self.coordinator.data or {}
        status = data.get("status", {})
        units = str(status.get("units", "")).upper()
        return (
            UnitOfTemperature.CELSIUS if units == "C" else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        # Return min value based on current unit
        if self.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            return 38  # ~100°F in Celsius
        return 100  # 100°F

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        # Return max value based on current unit
        if self.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            return 260  # ~500°F in Celsius
        return 500  # 500°F

    @property
    def native_value(self) -> float | None:
        """Return the current setpoint temperature."""
        return self._last_set_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the temperature setpoint."""
        try:
            # Store the value immediately
            self._last_set_value = value
            self.async_write_ha_state()  # Update UI immediately

            await self.client.set_hold_mode(value)
            _LOGGER.debug("Successfully set temperature setpoint to %s°", value)

        except Exception as err:
            _LOGGER.error("Failed to set temperature setpoint to %s°: %s", value, err)
            raise HomeAssistantError(
                f"Failed to set temperature setpoint to {value}°"
            ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        # Get current PSP from API
        current_psp = self._get_current_psp()

        # If we don't have a stored value, initialize it
        if self._last_set_value is None and current_psp is not None:
            self._last_set_value = current_psp

        # If PSP changed externally (from PiFire dashboard), update our stored value
        elif current_psp is not None and self._last_set_value != current_psp:
            _LOGGER.debug(
                "PSP changed externally from %s° to %s°, updating stored value",
                self._last_set_value,
                current_psp,
            )
            self._last_set_value = current_psp

        # Update the entity state
        self.async_write_ha_state()


class PiFirePrimePelletsGrams(NumberEntity):
    """Number entity for setting Prime Pellets grams amount."""

    _attr_has_entity_name = True
    _attr_name = "Prime Pellets Grams"
    _attr_mode = NumberMode.BOX
    _attr_step = 1
    _attr_min_value = 1
    _attr_max_value = 1000
    _attr_native_value = 100  # Default value
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_icon = "mdi:grain"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, entry: ConfigEntry, coordinator, client, device_info: DeviceInfo
    ) -> None:
        """Initialize the prime pellets grams number entity."""
        self._entry = entry
        self.coordinator = coordinator
        self.client = client
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_prime_pellets_grams"

    async def async_set_native_value(self, value: float) -> None:
        """Set the prime pellets grams amount."""
        # Just store the value, don't trigger priming
        self._attr_native_value = value
        self.async_write_ha_state()
