from __future__ import annotations

import logging
from typing import Any, Dict

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class PiFireError(RuntimeError):
    pass


class PiFireClient:
    """Minimal async client for PiFire."""

    def __init__(self, hass: HomeAssistant, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._session = async_get_clientsession(hass)

    async def get_current(self) -> Dict[str, Any]:
        url = f"{self._base}/api/current"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise PiFireError(f"HTTP {resp.status}: {text}")
                # PiFire sometimes sends content-type text; accept leniently
                return await resp.json(content_type=None)
        except Exception as err:
            raise PiFireError(str(err)) from err
