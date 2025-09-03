from __future__ import annotations

DOMAIN = "pifire"
CONF_BASE_URL = "base_url"

# We only ship sensors here; you can add other platforms later.
PLATFORMS: list[str] = ["sensor"]

# Keys in hass.data
CLIENT = "client"
COORDINATOR = "coordinator"

DEFAULT_UPDATE_SECONDS = 5
API_CURRENT = "/api/current"
