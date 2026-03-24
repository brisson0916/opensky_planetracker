"""Configuration for the OpenSky Flight Tracker."""
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TrackerConfig:
    """Configuration settings for the flight tracker."""

    # Location settings (Shenzhen/Hong Kong area)
    lat: float = float(os.getenv("MY_LAT"))
    lon: float = float(os.getenv("MY_LON"))
    radius_km: float = 12.5

    # Logging settings
    log_dir: str = "logs"

    # Token settings
    token_refresh_margin: int = 30

    # Default timezone
    default_timezone: str = "Asia/Hong_Kong"

    # API URLs
    opensky_url: str = "https://opensky-network.org/api/states/all"
    adsbdb_url: str = "https://api.adsbdb.com/v0/aircraft"
    auth_url: str = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

    # OpenSky field indices (for states array)
    class OpenSkyFields:
        """Indices for OpenSky states array."""
        CALLSIGN = 1
        COUNTRY = 2
        TIME = 3
        VELOCITY = 9
        HEADING = 10
        CLIMB_RATE = 11
        LONGITUDE = 5
        LATITUDE = 6
        ALTITUDE = 13
        ON_GROUND = 8

    # Discord Settings
    webhook_url = os.getenv("WEBHOOK_URL")

    # Deduplication Settings
    duplicate_ttl_minutes: int = 10