"""Constants for the PiFire integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "pifire"
CONF_HOST = "host"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
]
