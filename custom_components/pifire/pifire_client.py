from __future__ import annotations
import aiohttp
import logging
from typing import Any, Dict
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class PiFireClient:
    """Client for interacting with PiFire API."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize the client."""
        self._base = f"http://{host}".rstrip("/")
        self._session = async_get_clientsession(hass)

    async def get_current(self) -> Dict[str, Any]:
        """Get current status data from PiFire."""
        url = f"{self._base}/api/current"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.error("Failed to get current data: %s", err)
            raise

    async def get_hopper_data(self) -> Dict[str, Any]:
        """Get hopper/pellet data from PiFire."""
        url = f"{self._base}/api/hopper"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.debug("Failed to get hopper data (may not be supported): %s", err)
            return {}

    async def set_mode(self, mode: str) -> None:
        """Set the PiFire mode."""
        url = f"{self._base}/api/set/mode/{mode}"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                _LOGGER.debug("Successfully set PiFire mode to %s", mode)
        except Exception as err:
            _LOGGER.error("Failed to set mode %s: %s", mode, err)
            raise Exception(f"Failed to set mode to {mode}") from err

    async def set_hold_mode(self, temperature: float) -> None:
        """Set the PiFire to hold mode at specified temperature."""
        url = f"{self._base}/api/set/mode/hold/{temperature}"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                _LOGGER.debug(
                    "Successfully set PiFire to hold mode at %s°", temperature
                )
        except Exception as err:
            _LOGGER.error("Failed to set hold mode at %s°: %s", temperature, err)
            raise Exception(f"Failed to set hold mode") from err

    async def send_command(self, endpoint: str) -> None:
        """Send a command to the PiFire API."""
        url = f"{self._base}{endpoint}"
        try:
            async with self._session.post(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    raise Exception(f"API returned status {response.status}")
                _LOGGER.debug("Successfully sent command to %s", endpoint)
        except Exception as err:
            _LOGGER.error("Failed to send command to %s: %s", endpoint, err)
            raise

    async def set_p_mode(self, p_mode: int) -> None:
        """Set the P-Mode value."""
        url = f"{self._base}/api/set/pmode/{p_mode}"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                _LOGGER.debug("Successfully set P-Mode to P-%s", p_mode)
        except Exception as err:
            _LOGGER.error("Failed to set P-Mode to P-%s: %s", p_mode, err)
            raise Exception(f"Failed to set P-Mode to P-{p_mode}") from err

    async def prime_pellets(self, grams: int, next_mode: str) -> None:
        """Prime pellets with specified grams and next mode."""
        url = f"{self._base}/api/set/mode/prime/{grams}/{next_mode}"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                _LOGGER.debug(
                    "Successfully started pellet priming: %s grams, next mode: %s",
                    grams,
                    next_mode,
                )
        except Exception as err:
            _LOGGER.error(
                "Failed to prime pellets (%s grams, %s): %s", grams, next_mode, err
            )
            raise Exception(f"Failed to prime pellets") from err

    async def set_smoke_plus(self, enabled: bool) -> None:
        """Enable or disable Smoke Plus mode."""
        url = f"{self._base}/api/set/smokeplus/{str(enabled).lower()}"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                _LOGGER.debug("Successfully set Smoke Plus to %s", enabled)
        except Exception as err:
            _LOGGER.error("Failed to set Smoke Plus to %s: %s", enabled, err)
            raise Exception(f"Failed to set Smoke Plus to {enabled}") from err
