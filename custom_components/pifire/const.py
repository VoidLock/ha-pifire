from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from .const import DOMAIN, CONF_HOST

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST, default="pifire.local"): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            unique = f"http://{host}"
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="PiFire", data={CONF_HOST: host})
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
