from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_BASE_URL


DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BASE_URL, default="http://pifire.local:8080"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            unique_id = (user_input.get(CONF_BASE_URL) or "").rstrip("/") or "pifire_local"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="PiFire", data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_zeroconf(self, discovery_info: dict) -> FlowResult:
        host = discovery_info.get("host")
        port = discovery_info.get("port")
        base_url = f"http://{host}:{port}"

        await self.async_set_unique_id(base_url)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="PiFire", data={CONF_BASE_URL: base_url})
