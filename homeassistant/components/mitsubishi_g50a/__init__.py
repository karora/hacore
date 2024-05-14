"""The Mitsubishi G50a integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry, async_get

from .const import DOMAIN
from .g50a import MitsubishiG50a, enumerate_zones

PLATFORMS: list[Platform] = [Platform.CLIMATE]

bog = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Mitsubishi G50a from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    bog.info(f"module async_setup_entry: {config_entry}")
    hostname = config_entry.data[CONF_HOST]

    # Create a new MitsubishiG50a device
    zones = await enumerate_zones(hostname)
    device = MitsubishiG50a(hostname, zones)

    hass.data[DOMAIN][hostname] = device

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Register the device in the device registry
    device_registry: DeviceRegistry = async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, hostname)},
        manufacturer="Mitsubishi",
        model="G50a",
        name="Mitsubishi G50a",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# Service setup & definitions below this point
ATTR_ZONE = "zone"
DEFAULT_ZONE = "1"


# def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
#     """Set up is called when Home Assistant is loading our component."""

#     async def handle_g50_set_command(call):
#         """Handle the service call."""
#         zone_id = call.data.get(ATTR_ZONE, DEFAULT_ZONE)

#         bog.info(f"handle_g50_set_command: {zone_id}")
#         hass.states.set(f"{DOMAIN}.g50_set_command", zone_id)

#     bog.info(f"async_setup: {config} - adding handler for g50_set_command service.")
#     hass.services.async_register(DOMAIN, "g50_set_command", handle_g50_set_command)
