# mitsubishi_g50a.py
"""Support for Mitsubishi G50A devices."""

import logging
import time

import aiohttp
import defusedxml.ElementTree as ET

from homeassistant.components.climate import HVACAction, HVACMode

from .const import GET_COMMAND, MAX_ZONES, SET_COMMAND

bog = logging.getLogger(__name__)


def get_zone_name(zone: str | int) -> str:
    """Get the zone name based on the zone number."""
    # Change this to initialize the zone names based on values the
    # user has specified in the Home Assistant config for this module.
    zone_names = {
        "1": "Living Room",
        "2": "Kitchen",
        "3": "Hallway",
    }
    return zone_names.get(str(zone), f"Zone {zone}")


def map_hvac_mode_to_mode(hvac_mode: HVACMode) -> str:
    """Map the HVAC mode to a mode."""
    if hvac_mode == HVACMode.FAN_ONLY:
        return "FAN"
    return hvac_mode.upper()


def map_mode_to_hvac_mode(mode: str, drive) -> HVACMode:
    """Map the mode to an HVAC mode."""
    if drive == "OFF":
        return HVACMode.OFF
    if mode == "COOL":
        return HVACMode.COOL
    if mode == "HEAT":
        return HVACMode.HEAT
    if mode == "FAN":
        return HVACMode.FAN_ONLY
    if mode == "DRY":
        return HVACMode.DRY
    return HVACMode.OFF


def map_mode_to_hvac_action(mode: str, drive) -> HVACAction:
    """Map the mode to an HVAC action."""
    if drive == "OFF":
        return HVACAction.IDLE
    if mode == "COOL":
        return HVACAction.COOLING
    if mode == "HEAT":
        return HVACAction.HEATING
    if mode == "FAN":
        return HVACAction.FAN
    if mode == "DRY":
        return HVACAction.DRYING
    return HVACAction.IDLE


def map_fan_speed_to_fan_mode(fan_speed) -> str:
    """Map the fan speed to a fan mode."""
    # When you send a command to *set* the fan_speed to "LOW" the G50A
    # will set the fan speed to low, but it will return "MID2" :-/
    # If you tell it to set the fan speed to "MID2" it will set it to "MID2"
    # but this could well be faster than you got setting it to "LOW" :-/
    # I think this mess all comes about because the actual head units attached
    # are what is ultimately responding to the command, so they're maintaining
    # their own state and the G50A is just sending them the Mnet commands.
    if fan_speed == "MID1":
        return "medium"
    if fan_speed == "MID2":
        return "low"  # Maybe this'll do the trick?
    return str(fan_speed.lower())


def map_fan_mode_to_fan_speed(fan_mode: str) -> str:
    """Map the fan mode to a fan speed."""
    if fan_mode == "medium":
        return "MID1"
    # In this case we just ignore the existence of "MID2" entirely
    return fan_mode.upper()


def map_swing_to_air_direction(swing: str) -> str:
    """Map the swing mode to an air direction."""
    if swing == "off":
        return "MID1"
    if swing == "on":
        return "SWING"
    if swing == "both":
        return "MID2"
    return swing.upper()


def map_air_direction_to_swing(air_direction) -> str:
    """Map the air direction to a swing mode."""
    if air_direction == "MID1":
        return "off"
    if air_direction == "SWING":
        return "on"
    if air_direction == "MID2":
        return "both"
    return str(air_direction.lower())


def construct_request_xml(command: str, mnet_xml: str) -> str:
    """Build the XML request for the command with the supplied mnet XML."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <Packet>
        <Command>{command}</Command>
        <DatabaseManager>
            {mnet_xml}
        </DatabaseManager>
    </Packet>"""


def xml_mnet_for_zone(zone_id: str) -> str:
    """Build the XML request Mnet for a single zone."""
    return f'<Mnet Group="{zone_id}" SetTemp="*" InletTemp="*" Drive="*" Mode="*" FanSpeed="*" AirDirection="*" />'


def xml_request_for_zones(command: str, no_zones: int) -> str:
    """Build the XML request for the command and number of zones."""
    mnet_xml = ""

    for zone_id in range(1, no_zones + 1):
        mnet_xml += xml_mnet_for_zone(f"{zone_id}")

    return construct_request_xml(command, mnet_xml)


async def send_request(hostname: str, xml_request: str, timeout=30) -> str:
    """Send a request to the G50A device."""
    url = f"http://{hostname}/servlet/MIMEReceiveServlet"
    headers = {
        "content-type": "text/xml",
        "User-Agent": "homeassistant+mitsuibishi_g50a/1.0",
    }
    bog.debug(f"Sending request: hostname={hostname}, XML={xml_request}")
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            url, data=xml_request, headers=headers, timeout=timeout
        ) as response,
    ):
        return await response.text()


class G50Zone:
    """Class representing a G50 zone."""

    def __init__(self, name: str, **kwargs) -> None:
        """Initialize the class."""
        self.name = name
        set_temp = kwargs.get("set_temp")
        if set_temp is not None:
            self.set_temp = float(set_temp)
        inlet_temp = kwargs.get("inlet_temp")
        if inlet_temp is not None:
            self.inlet_temp = float(inlet_temp)
        self.drive = kwargs.get("drive")
        mode = kwargs.get("mode")
        self._mode = str(mode)
        self._fan_speed = kwargs.get("fan_speed")
        self._air_direction = kwargs.get("air_direction")
        self.last_updated = kwargs.get("last_updated")

    def __repr__(self):
        """Return the representation of the class."""

    def update_zone(self, name: str, **kwargs) -> None:
        """Update the class."""
        self.name = name
        set_temp = kwargs.get("set_temp")
        if set_temp is not None:
            self.set_temp = float(set_temp)
        inlet_temp = kwargs.get("inlet_temp")
        if inlet_temp is not None:
            self.inlet_temp = float(inlet_temp)
        self.drive = kwargs.get("drive")
        mode = kwargs.get("mode")
        self._mode = str(mode)
        self._fan_speed = kwargs.get("fan_speed")
        self._air_direction = kwargs.get("air_direction")
        self.last_updated = kwargs.get("last_updated")

    def set_mode(self, mode: str) -> None:
        """Set the mode of the zone."""
        self._mode = mode

    def set_air_direction(self, air_direction: str) -> None:
        """Set the air direction of the zone."""
        self._air_direction = air_direction

    def set_fan_speed(self, fan_speed: str) -> None:
        """Set the fan speed of the zone."""
        self._fan_speed = fan_speed

    @property
    def g50_mode(self) -> str:
        """Return the g50_mode of the zone."""
        return self._mode

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the hvac_mode of the zone."""
        return map_mode_to_hvac_mode(self._mode, self.drive)

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVACAction of the zone."""
        return map_mode_to_hvac_action(self._mode, self.drive)

    @property
    def fan_mode(self) -> str:
        """Return the fan_mode of the zone."""
        return map_fan_speed_to_fan_mode(self._fan_speed)

    @property
    def swing_mode(self) -> str:
        """Return the swing_mode of the zone."""
        return map_air_direction_to_swing(self._air_direction)


async def enumerate_zones(hostname: str, timeout=30) -> dict[str, G50Zone]:
    """Enumerate the zones."""
    enumerated_zones: dict[str, G50Zone] = {}
    for zone_id in range(1, MAX_ZONES + 1):
        mnet_xml = xml_mnet_for_zone(f"{zone_id}")
        bog.info(f"Requesting zone info:\n   {mnet_xml}")
        xml_request = construct_request_xml(GET_COMMAND, mnet_xml)
        response = await send_request(hostname, xml_request, timeout=timeout)
        root = ET.fromstring(response)
        errors = root.findall(".//ERROR")
        if len(errors) > 0:
            bog.info(f"Found {zone_id - 1} zones.")
            return (
                enumerated_zones  # normally return from here with fewer than MAX_ZONES
            )
        for mnet in root.findall(".//Mnet"):
            zone_id = mnet.get("Group")
            enumerated_zones[f"{zone_id}"] = G50Zone(
                get_zone_name(zone_id),
                set_temp=mnet.get("SetTemp"),
                inlet_temp=mnet.get("InletTemp"),
                drive=mnet.get("Drive"),
                mode=mnet.get("Mode"),
                fan_speed=mnet.get("FanSpeed"),
                air_direction=mnet.get("AirDirection"),
                last_updated=time.time_ns(),
            )
    return enumerated_zones  # return here if exceeded MAX_ZONES


class MitsubishiG50a:
    """Class representing MitsubishiG50a."""

    def __init__(self, hostname: str, zones: dict[str, G50Zone]) -> None:
        """Initialize the class."""
        self.hostname = hostname
        self.last_updated = 0
        self.unique_id = f"mitsubishi_g50a_{hostname}"
        self.zones = zones
        #     "1": G50Zone("Living Room"),
        #     "2": G50Zone("Kitchen"),
        #     "3": G50Zone("Hallway"),
        # }

    def parse_response(self, response: str) -> None:
        """Parse the response from the G50A device."""
        bog.debug(f"Parsing response: hostname={self.hostname}, response={response}")
        root = ET.fromstring(response)
        for mnet in root.findall(".//Mnet"):
            zone_id = mnet.get("Group")
            if zone_id not in self.zones:
                bog.error(f"Adding zone: {zone_id}")
                self.zones[zone_id] = G50Zone(
                    get_zone_name(zone_id),
                    set_temp=mnet.get("SetTemp"),
                    inlet_temp=mnet.get("InletTemp"),
                    drive=mnet.get("Drive"),
                    mode=mnet.get("Mode"),
                    fan_speed=mnet.get("FanSpeed"),
                    air_direction=mnet.get("AirDirection"),
                    last_updated=self.last_updated,
                )
            else:
                self.zones[zone_id].update_zone(
                    get_zone_name(zone_id),
                    set_temp=mnet.get("SetTemp"),
                    inlet_temp=mnet.get("InletTemp"),
                    drive=mnet.get("Drive"),
                    mode=mnet.get("Mode"),
                    fan_speed=mnet.get("FanSpeed"),
                    air_direction=mnet.get("AirDirection"),
                    last_updated=self.last_updated,
                )

    async def turn_on_off(self, zone_id: str, on_off: str) -> None:
        """Turn zone on or off."""
        drive = on_off.upper()
        if self.zones[zone_id].drive == drive:
            bog.info(f"Zone {zone_id} is already {drive}")
            return
        mnet_xml = f'<Mnet Group="{zone_id}" Drive="{drive}""/>'
        bog.info(f"Sending Mnet command: {mnet_xml}")
        xml_request = construct_request_xml(SET_COMMAND, mnet_xml)
        await send_request(self.hostname, xml_request)
        self.zones[zone_id].drive = drive

    async def set_system_mode(self, zone_id: str, hvac_mode: HVACMode) -> None:
        """Set the state of a zone."""
        new_mode = map_hvac_mode_to_mode(hvac_mode)
        mnet_xml = f'<Mnet Group="{zone_id}" Drive="ON" Mode="{new_mode}"/>'
        if hvac_mode == HVACMode.OFF:
            mnet_xml = f'<Mnet Group="{zone_id}" Drive="OFF"/>'
        bog.info(f"Sending Mnet command:\n   {mnet_xml}")
        xml_request = construct_request_xml(SET_COMMAND, mnet_xml)
        await send_request(self.hostname, xml_request)

    async def set_swing_mode(self, zone_id: str, swing_mode) -> None:
        """Set the swing mode for the zone."""
        air_direction = map_swing_to_air_direction(swing_mode)
        mnet_xml = f'<Mnet Group="{zone_id}" AirDirection="{air_direction}"/>'
        bog.info(f"Sending Mnet command:\n   {mnet_xml}")
        xml_request = construct_request_xml(SET_COMMAND, mnet_xml)
        await send_request(self.hostname, xml_request)
        self.zones[zone_id].set_air_direction(air_direction)

    async def set_fan_mode(self, zone_id: str, fan_mode) -> None:
        """Set the fan mode for the zone."""
        fan_speed = map_fan_mode_to_fan_speed(fan_mode)
        mnet_xml = f'<Mnet Group="{zone_id}" FanSpeed="{fan_speed}"/>'
        bog.info(f"Sending Mnet command:\n   {mnet_xml}")
        xml_request = construct_request_xml(SET_COMMAND, mnet_xml)
        await send_request(self.hostname, xml_request)
        self.zones[zone_id].set_fan_speed(fan_speed)

    async def set_temperature(self, zone_id: str, target_temperature: float) -> None:
        """Set the temperature for the zone."""
        mnet_xml = f'<Mnet Group="{zone_id}" SetTemp="{target_temperature}"/>'
        bog.info(f"Sending Mnet command:\n   {mnet_xml}")
        xml_request = construct_request_xml(SET_COMMAND, mnet_xml)
        await send_request(self.hostname, xml_request)
        self.zones[zone_id].set_temp = target_temperature

    async def update_zone(self, zone_id: str) -> None:
        """Update the state of a single zone."""
        mnet_xml = xml_mnet_for_zone(zone_id)
        bog.info(f"Requesting zone update:\n   {mnet_xml}")
        xml_request = construct_request_xml(GET_COMMAND, mnet_xml)
        response = await send_request(self.hostname, xml_request)
        self.parse_response(response)

    async def update_zones(self) -> None:
        """Update the state of all zones."""
        since = time.time_ns() - 0  # self.last_updated
        if since > 100_000_000:
            self.last_updated = time.time_ns()
            xml_request = xml_request_for_zones(GET_COMMAND, 3)
            bog.info(f"Requesting update: XML={xml_request}, since={since}")
            response = await send_request(self.hostname, xml_request)
            self.parse_response(response)
        else:
            bog.info("Skipping update: since={since}")
