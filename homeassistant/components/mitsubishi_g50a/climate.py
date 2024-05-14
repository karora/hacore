# climate.py
"""Support "Climate" interface for Mitsubishi G50A devices."""

import logging
from typing import Any

from homeassistant.components import logbook
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .g50a import G50Zone, MitsubishiG50a

bog = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Mitsubishi G50a climate platform."""

    # Get the MitsubishiG50a device from the hass.data dictionary
    bog.info(f"climate setup_platform: {config}")
    hostname = config[CONF_HOST]
    device = hass.data[DOMAIN][hostname]

    # Create a list comprehension to create a list of MitsubishiG50aClimate entities
    entities = [
        MitsubishiG50aClimate(device, zone_id, zone)
        for zone_id, zone in device.zones.items()
    ]

    # Add the entities to Home Assistant
    add_entities(entities, True)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Mitsubishi G50a climate platform."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mitsubishi G50a from a config entry."""

    bog.info(f"climate async_setup_entry: {config_entry}")
    hostname = config_entry.data[CONF_HOST]

    # Use existing MitsubishiG50a device from the hass.data dictionary
    device: MitsubishiG50a = hass.data[DOMAIN][hostname]

    # Create a list comprehension to create a list of MitsubishiG50aClimate entities
    entities = [
        MitsubishiG50aClimate(device, zone_id, zone)
        for zone_id, zone in device.zones.items()
    ]

    # Add the entities to Home Assistant
    async_add_entities(entities, True)


class MitsubishiG50aClimate(ClimateEntity):
    """Representation of a Mitsubishi G50a climate device."""

    def __init__(self, device: MitsubishiG50a, zone_id: str, zone: G50Zone) -> None:
        """Initialize the climate device."""
        self._g50 = device
        self._zone_id = zone_id
        self._zone = zone
        bog.info(f"Initialising zone {zone_id}: {zone.name}")

        # All temperatures are in Celsius
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_WHOLE

        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.AUTO,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]
        self._attr_fan_modes = ["auto", "low", "medium", "high"]
        self._attr_swing_modes = ["on", "off", "both", "vertical", "horizontal"]
        self._attr_supported_features: ClimateEntityFeature = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._attr_max_temp = 35
        self._attr_min_temp = 5
        self._attr_target_temperature_step = 1

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the entity."""
        return f"mitsubishi_g50a_{self._g50.hostname}_{self._zone_id}"

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._zone.name

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        # bog.info(f"Current hvac_action: {self._zone_id}, {self._zone.hvac_action}")
        return self._zone.hvac_action

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        # bog.info(f"Current hvac_mode: {self._zone_id}, {self._zone.hvac_mode}")
        return self._zone.hvac_mode

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        # bog.info(f"Current fan_mode: {self._zone_id}, {self._zone.fan_mode}")
        return self._zone.fan_mode

    @property
    def swing_mode(self) -> str:
        """Return the current swing mode."""
        # bog.info(f"Current swing_mode: {self._zone_id}, {self._zone.swing_mode}")
        return self._zone.swing_mode

    @property
    def target_temperature(self) -> float:
        """Return the current target temperature."""
        return self._zone.set_temp

    @property
    def target_temperature_high(self) -> float:
        """Return the current target temperature."""
        return self._zone.set_temp

    @property
    def target_temperature_low(self) -> float:
        """Return the current target temperature."""
        return self._zone.set_temp

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    async def async_update(self) -> None:
        """Fetch new state data for this entity.

        This is the only method that should fetch new data for Home Assistant.
        """
        action_was = self.hvac_action
        await self._g50.update_zone(self._zone_id)
        if self.hvac_action != action_was:
            logbook.log_entry(
                self.hass, self.name, f"State changed to {self.hvac_action}"
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._g50.set_system_mode(self._zone_id, hvac_mode)
        logbook.log_entry(self.hass, self.name, f"HVAC Mode set to {hvac_mode}")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target = kwargs.get(ATTR_TEMPERATURE)
        self.hass.async_create_task(self.log_temperature(target))
        if target is not None:
            await self._g50.set_temperature(self._zone_id, float(target))
            logbook.log_entry(
                self.hass, self.name, f"Target temperature set to {target}"
            )

    async def async_turn_on(self) -> None:
        """Turn on the zone."""
        await self._g50.turn_on_off(self._zone_id, "ON")
        logbook.log_entry(self.hass, self.name, "Climate turned on")

    async def async_turn_off(self) -> None:
        """Turn off the zone."""
        await self._g50.turn_on_off(self._zone_id, HVACMode.OFF)
        logbook.log_entry(self.hass, self.name, "Climate turned off")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._g50.set_fan_mode(self._zone_id, fan_mode)
        logbook.log_entry(self.hass, self.name, f"Fan Mode set to {fan_mode}")

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        await self._g50.set_swing_mode(self._zone_id, swing_mode)
        logbook.log_entry(self.hass, self.name, f"Swing Mode set to {swing_mode}")

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        signal = f"{self.unique_id}_set_command"
        async_dispatcher_connect(
            # The Hass Object
            self.hass,
            # The Signal to listen for.
            # Try to make it unique per entity instance
            # so include something like entity_id
            # or other unique data from the service call
            signal,
            # Function handle to call when signal is received
            self.async_turn_on,
        )

    # Implement the required properties and methods for the ClimateEntity here...


class MitsubishiG50aClimateSensor(Entity):
    """Representation of a sensor for Mitsubishi G50a climate properties."""

    def __init__(
        self, climate_entity: MitsubishiG50aClimate, property_name: str
    ) -> None:
        """Initialize the sensor."""
        self._climate_entity = climate_entity
        self._property_name = property_name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._climate_entity.name} {self._property_name}"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return getattr(self._climate_entity, self._property_name)

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._climate_entity.unique_id}_{self._property_name}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for the sensor."""
        return self._climate_entity.device_info

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state, False otherwise."""
        return self._climate_entity.should_poll

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        await self._climate_entity.async_update()

    async def async_added_to_hass(self) -> None:
        """Run when the sensor is added to Home Assistant."""
        self._climate_entity.async_on_remove(
            self._climate_entity.async_add_listener(self.async_write_ha_state)
        )
