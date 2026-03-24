"""Data models for the OpenSky Flight Tracker."""
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass
class FlightDetails:
    """Structured flight information from OpenSky and ADSBDB."""

    callsign: str
    route_code: str
    flight_number: str
    airline_name: str
    origin_city: str
    origin_country: str
    dest_city: str
    dest_country: str
    country: str
    altitude: float | None
    velocity: float | None
    heading: float | None
    climb_rate: float | None
    timestamp: datetime
    distance_km: float

    @property
    def is_unknown(self) -> bool:
        """Check if flight information is unknown."""
        return self.flight_number == 'unknown'

    @property
    def heading_direction(self) -> str:
        """Get human-readable heading direction."""
        if self.heading is None:
            return ''
        return to_quadrant_bearing(self.heading)

    def format_summary(self, timezone_str: str) -> str:
        """Generate human-readable flight summary."""
        if self.is_unknown:
            route_info = f"Route: {self.route_code}"
            summary = ""
        else:
            route_info = f"Route: {self.route_code}"
            summary = (
                f"This is {self.airline_name}'s flight {self.flight_number} "
                f"from {self.origin_city}, {self.origin_country} to "
                f"{self.dest_city}, {self.dest_country}."
            )

        formatted_time = datetime.fromtimestamp(self.timestamp.timestamp(), ZoneInfo(timezone_str))
        heading = f"(heading {self.heading_direction})" if self.heading else ""

        return f'Plane Spotted {self.distance_km}km away! ({formatted_time})', f"""
Flight: {self.callsign if self.is_unknown else self.flight_number}
{route_info}
State of Registry: {self.country}
Altitude: {self._format_altitude()}
Velocity: {self._format_velocity()} {heading}
Climb Rate: {self._format_climb_rate()}

{summary if summary else ''}
Track it: https://www.flightradar24.com/{self.callsign}
"""

    def _format_altitude(self) -> str:
        if self.altitude is None:
            return "Unknown"
        return f"{round(self.altitude, 1)} meters"

    def _format_velocity(self) -> str:
        if self.velocity is None:
            return "Unknown"
        return f"{round(self.velocity * 3.6, 1)} km/h"

    def _format_climb_rate(self) -> str:
        if self.climb_rate is None:
            return "Unknown"
        return f"{round(self.climb_rate, 1)} m/s"


def to_quadrant_bearing(angle: float) -> str:
    """Convert heading angle to compass direction."""
    angle = angle % 360
    if 0 <= angle < 90:
        return f"N {angle:.1f}° E"
    elif 90 <= angle < 180:
        return f"S {180 - angle:.1f}° E"
    elif 180 <= angle < 270:
        return f"S {angle - 180:.1f}° W"
    else:
        return f"N {360 - angle:.1f}° W"
