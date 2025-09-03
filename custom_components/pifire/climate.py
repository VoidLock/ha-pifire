"""PiFire climate platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    PRESET_NONE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# PiFire mode presets
PRESET_STARTUP = "startup"
PRESET_SMOKE = "smoke"
PRESET_HOLD = "hold"

# Map PiFire modes to presets
PIFIRE_MODE_TO_PRESET = {
    "startup": PRESET_STARTUP,
    "smoke": PRESET_SMOKE,
    "hold": PRESET_HOLD,
    "stop": PRESET_NONE,
}

PRESET_TO_PIFIRE_MODE = {
    PRESET_STARTUP: "startup",
    PRESET_SMOKE: "smoke",
    PRESET_HOLD: "hold",
    PRESET_NONE: "stop",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PiFire climate entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]

    async_add_entities([PiFireThermostat(entry, coordinator, client)])


class PiFireThermostat(ClimateEntity):
    """PiFire thermostat entity."""

    _attr_has_entity_name = True
    _attr_name = "Thermostat"
    _attr_icon = "mdi:thermostat"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [PRESET_NONE, PRESET_STARTUP, PRESET_SMOKE, PRESET_HOLD]
    _attr_min_temp = 100
    _attr_max_temp = 500
    _attr_target_temperature_step = 1

    def __init__(self, entry: ConfigEntry, coordinator, client) -> None:
        """Initialize the thermostat."""
        self._entry = entry
        self.coordinator = coordinator
        self.client = client
        self._attr_unique_id = f"{entry.entry_id}_thermostat"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="PiFire",
            manufacturer="PiFire",
            model="Grill Controller",
        )

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        data = self.coordinator.data or {}
        status = data.get("status", {})
        units = str(status.get("units", "")).upper()
        return (
            UnitOfTemperature.CELSIUS if units == "C" else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return 38  # ~100°F in Celsius
        return 100  # 100°F

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return 260  # ~500°F in Celsius
        return 500  # 500°F

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        data = self.coordinator.data or {}
        current = data.get("current", {})
        pmap = current.get("P", {})

        # Get grill temperature from P["Grill"]
        grill_temp = pmap.get("Grill")
        try:
            return float(grill_temp) if grill_temp is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self.coordinator.data or {}
        current = data.get("current", {})

        # Get setpoint from PSP (Primary Setpoint)
        psp = current.get("PSP")
        if psp is not None:
            try:
                return float(psp)
            except (TypeError, ValueError):
                pass

        # Fallback to P.Grill setpoint
        pmap = current.get("P", {})
        setpoint = pmap.get("Grill")
        try:
            return float(setpoint) if setpoint is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        data = self.coordinator.data or {}
        status = data.get("status", {})
        pifire_mode = status.get("mode", "").lower()

        # Simple on/off based on stop mode
        return HVACMode.OFF if pifire_mode == "stop" else HVACMode.HEAT

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        data = self.coordinator.data or {}
        status = data.get("status", {})
        pifire_mode = status.get("mode", "").lower()

        return PIFIRE_MODE_TO_PRESET.get(pifire_mode, PRESET_NONE)

    @property
    def hvac_action(self) -> str | None:
        """Return current HVAC action."""
        data = self.coordinator.data or {}
        status = data.get("status", {})
        pifire_mode = status.get("mode", "").lower()

        if pifire_mode == "stop":
            return "off"
        elif pifire_mode in ("startup", "smoke", "hold"):
            # Check if we're actively heating by looking at fan/auger status
            outpins = status.get("outpins", {})
            if outpins.get("fan") or outpins.get("auger"):
                return "heating"
            return "idle"

        return "off"

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            if hvac_mode == HVACMode.OFF:
                await self.client.set_mode("stop")
                _LOGGER.debug("Set PiFire to stop mode")
            elif hvac_mode == HVACMode.HEAT:
                # When turning on, use hold mode with current or default temperature
                target_temp = self.target_temperature or 225
                await self.client.set_hold_mode(target_temp)
                _LOGGER.debug("Set PiFire to hold mode at %s°", target_temp)
            else:
                raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")

            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set HVAC mode to %s: %s", hvac_mode, err)
            raise HomeAssistantError(f"Failed to set mode to {hvac_mode}") from err

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        try:
            pifire_mode = PRESET_TO_PIFIRE_MODE.get(preset_mode)
            if pifire_mode is None:
                raise HomeAssistantError(f"Unsupported preset mode: {preset_mode}")

            if pifire_mode == "hold":
                # For hold mode, use current target temperature or default
                target_temp = self.target_temperature or 225
                await self.client.set_hold_mode(target_temp)
                _LOGGER.debug("Set PiFire to hold mode at %s°", target_temp)
            else:
                await self.client.set_mode(pifire_mode)
                _LOGGER.debug("Set PiFire mode to %s", pifire_mode)

            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set preset mode to %s: %s", preset_mode, err)
            raise HomeAssistantError(f"Failed to set preset to {preset_mode}") from err

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self.client.set_hold_mode(temperature)
            _LOGGER.debug("Set PiFire temperature to %s°", temperature)

            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set temperature to %s°: %s", temperature, err)
            raise HomeAssistantError(
                f"Failed to set temperature to {temperature}°"
            ) from err

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        data = self.coordinator.data or {}
        status = data.get("status", {})

        attributes = {}

        # Add PiFire-specific mode
        pifire_mode = status.get("mode")
        if pifire_mode:
            attributes["pifire_mode"] = pifire_mode

        # Add output pin status
        outpins = status.get("outpins", {})
        if outpins:
            attributes["fan"] = outpins.get("fan", False)
            attributes["auger"] = outpins.get("auger", False)
            attributes["igniter"] = outpins.get("igniter", False)

        return attributes if attributes else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()
