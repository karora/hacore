"""Config flow for Mitsubishi G50a integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .g50a import MitsubishiG50a, enumerate_zones

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional("description", default=""): str,
    }
)


async def validate_input(hass: HomeAssistant | None, user_input: dict[str, Any]):
    """Validate the user input."""
    hostname = user_input[CONF_HOST]
    zones = await enumerate_zones(hostname)
    g50a = MitsubishiG50a(hostname, zones)
    return {
        "title": hostname,
        "zones": g50a.zones,
        "unique_id": f"mitsubishi_g50a_{hostname}",
        CONF_HOST: hostname,
    }


class G50aConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mitsubishi G50a."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the class."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_description(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the description step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate the user input for description
            if "description" in user_input:
                description = user_input["description"]
                # Save the description in the data dictionary
                self.data["description"] = description
                return self.async_create_entry(title=self.data["title"], data=self.data)
        return self.async_show_form(
            step_id="description",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
