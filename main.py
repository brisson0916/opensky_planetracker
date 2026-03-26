"""OpenSky Flight Tracker - Main entry point."""
import json
import logging
import os
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from geopy.distance import geodesic
from geopy.point import Point
from timezonefinder import TimezoneFinder

import folium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from config import TrackerConfig
from models import FlightDetails

from discord_webhook import DiscordWebhook, DiscordEmbed

# Load environment variables at startup
load_dotenv()

# Configure logging
log_directory = 'logs'
log_filename = 'flight_tracker.log'
log_filepath = os.path.join('.',log_directory, log_filename)
os.makedirs(log_directory, exist_ok=True)

logging.basicConfig(
    filename=log_filepath,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='a',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('flight_tracker')

class TokenManager:
    """Manages OpenSky API authentication tokens."""

    def __init__(self, config: TrackerConfig):
        self.config = config
        self.token = None
        self.expires_at = None

    def get_token(self) -> str:
        """Return a valid access token, refreshing automatically if needed."""
        if self.token and self.expires_at and datetime.now() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self) -> str:
        """Fetch a new access token from the OpenSky authentication server."""
        logger.info("Refreshing OpenSky token...")
        r = requests.post(
            self.config.auth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": os.getenv("CLIENT_ID"),
                "client_secret": os.getenv("CLIENT_SECRET"),
            },
        )
        r.raise_for_status()

        data = r.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = datetime.now() + timedelta(
            seconds=expires_in - self.config.token_refresh_margin
        )
        logger.info("Token refreshed successfully")
        return self.token

    def headers(self) -> dict:
        """Return request headers with a valid Bearer token."""
        return {"Authorization": f"Bearer {self.get_token()}"}

class PlaneHistory:
    """Manages plane history to avoid duplicate notifications."""

    def __init__(self, filepath: str, ttl_minutes: int = 10):
        self.filepath = filepath
        self.ttl_seconds = ttl_minutes * 60
        self._load_and_cleanup()

    def _load_and_cleanup(self):
        """Load JSON file and remove expired entries."""
        if not os.path.exists(self.filepath):
            self.data = {}
            return

        try:
            with open(self.filepath, 'r') as f:
                self.data = json.load(f)
        except (json.JSONDecodeError, IOError):
            self.data = {}

        # Remove expired entries
        now = time.time()
        self.data = {k: v for k, v in self.data.items()
                    if now - v <= self.ttl_seconds}

    def is_duplicate(self, callsign: str) -> bool:
        """Check if callsign was already notified within TTL."""
        return callsign in self.data

    def mark_seen(self, callsign: str):
        """Mark callsign as notified."""
        self.data[callsign] = time.time()
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f)


class FlightTracker:
    """Main class for tracking nearby flights."""

    def __init__(self, config: TrackerConfig | None = None):
        self.config = config or TrackerConfig()
        self.center = Point(self.config.lat, self.config.lon)
        self.token_manager = TokenManager(self.config)
        self._timezone = None

        # Initialize plane history for deduplication
        history_filepath = os.path.join(self.config.log_dir, 'spotted_planes.json')
        self.plane_history = PlaneHistory(history_filepath, self.config.duplicate_ttl_minutes)

    @property
    def timezone(self) -> str:
        """Get timezone for the tracked location (cached)."""
        if self._timezone is None:
            self._timezone = get_timezone(self.center.latitude, self.center.longitude)
        return self._timezone

    def _calculate_bounds(self) -> dict:
        """Calculate bounding box for API query."""
        half_side = self.config.radius_km
        return {
            'north': round(geodesic(kilometers=half_side).destination(self.center, 0).latitude, 6),
            'south': round(geodesic(kilometers=half_side).destination(self.center, 180).latitude, 6),
            'east': round(geodesic(kilometers=half_side).destination(self.center, 90).longitude, 6),
            'west': round(geodesic(kilometers=half_side).destination(self.center, 270).longitude, 6),
        }

    def get_nearby_flights(self) -> dict:
        """Fetch all flights within the bounding box."""
        bounds = self._calculate_bounds()

        url = (
            f"{self.config.opensky_url}"
            f"?lamin={bounds['south']}&lamax={bounds['north']}"
            f"&lomin={bounds['west']}&lomax={bounds['east']}"
        )

        response = requests.get(url, headers=self.token_manager.headers())
        logger.info(f"Fetching flight data from OpenSky API...")
        if response.status_code == 200:
            data = response.json()
            flight_count = len(data.get('states') or [])

            if flight_count > 0:
                logger.info(f"Found {flight_count} flights in range")
            return data
        
        else:
            logger.error(f"Connection to Opensky API failed (status {response.status_code})")
            response.raise_for_status() 

    def find_closest_flight(self, flight_data: dict) -> tuple[int, float]:
        """Find the closest flight to the center point."""
        states = flight_data.get('states')
        if not states:
            return None, None
        
        # Filter to only airborne planes
        airborne_planes = [
            (idx, plane) for idx, plane in enumerate(states) if not plane[TrackerConfig.OpenSkyFields.ON_GROUND]
        ]
        if not airborne_planes:
            logger.warning(f"No airborne flights near you.")
            return None, None

        closest_idx, closest_distance = 0, float('inf')

        for idx, plane in airborne_planes:
            distance_km = geodesic(
                self.center,
                (plane[TrackerConfig.OpenSkyFields.LATITUDE],
                 plane[TrackerConfig.OpenSkyFields.LONGITUDE])
            ).kilometers
            if distance_km < closest_distance:
                closest_idx = idx
                closest_distance = distance_km

        logger.info(f"Closest flight found: {round(closest_distance, 1)}km away")
        return closest_idx, round(closest_distance, 1)

    def get_route_info(self, callsign: str) -> dict:
        """Fetch route information from ADSBDB API."""
        url = f"{self.config.adsbdb_url}/40451C?callsign={callsign}"
        logger.info(f"Fetching route info for {callsign} from adsbdb API...")
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            route = data['response']['flightroute']
            logger.info(f"Route found: {route['origin']['iata_code']}-{route['destination']['iata_code']}")
            return {
                'route_code': f"{route['origin']['iata_code']}-{route['destination']['iata_code']}",
                'flight_number': route['callsign_iata'],
                'airline_name': route['airline']['name'],
                'origin_city': route['origin']['municipality'],
                'origin_country': route['origin']['country_name'],
                'dest_city': route['destination']['municipality'],
                'dest_country': route['destination']['country_name'],
            }

        # Return unknown values
        logger.error(f"Connection to adsbdb API failed (status{response.status_code})")
        return {
            key: 'unknown'
            for key in ['route_code', 'flight_number', 'airline_name',
                        'origin_city', 'origin_country', 'dest_city', 'dest_country']
        }

    def extract_flight_details(self, flight_data: dict, idx: int, distance_km: float) -> FlightDetails:
        """Extract and format flight details from raw API data."""
        states = flight_data['states']
        plane = states[idx]
        Fields = TrackerConfig.OpenSkyFields

        callsign = plane[Fields.CALLSIGN] or 'Unknown'
        route_info = self.get_route_info(callsign.strip())

        return FlightDetails(
            callsign=callsign,
            route_code=route_info['route_code'],
            flight_number=route_info['flight_number'],
            airline_name=route_info['airline_name'],
            origin_city=route_info['origin_city'],
            origin_country=route_info['origin_country'],
            dest_city=route_info['dest_city'],
            dest_country=route_info['dest_country'],
            country=plane[Fields.COUNTRY] or 'Unknown',
            longitude = plane[Fields.LONGITUDE],
            latitude = plane[Fields.LATITUDE],
            altitude=plane[Fields.ALTITUDE],
            velocity=plane[Fields.VELOCITY],
            heading=plane[Fields.HEADING],
            climb_rate=plane[Fields.CLIMB_RATE],
            timestamp=datetime.fromtimestamp(plane[Fields.TIME]),
            distance_km=distance_km,
        )

    def run(self):
        """Main execution: find and display closest flight."""
        logger.info("=" * 50)
        logger.info(f"Flight tracker started - Location: ({self.config.lat}, {self.config.lon}), Radius: {self.config.radius_km}km")

        flight_data = self.get_nearby_flights()
        closest_idx, distance = self.find_closest_flight(flight_data)

        if closest_idx is None:
            logger.warning("No flights found in range")
            print('No Flights near you.')
            return

        flight_details = self.extract_flight_details(flight_data, closest_idx, distance)

        text_header, text_message = flight_details.format_summary(self.timezone)
        print(text_header,text_message)

        # Check if plane was spotted within 10 minutes (to prevent duplicate notifications)
        callsign = flight_details.callsign
        if self.plane_history.is_duplicate(callsign):
            logger.info(f"Skipping notification for {callsign} - already notified within {self.config.duplicate_ttl_minutes} minutes")
            return

        # Mark as seen and send notification
        self.plane_history.mark_seen(callsign)
        map_path= self.generate_static_map(flight_details)
        self.send_discord_notification(text_header, text_message, map_path)

    def generate_static_map(self, flight_details: FlightDetails) -> str:
        """Generate a static PNG map showing user location and aircraft location.

        Args:
            flight_details: FlightDetails object containing aircraft position

        Returns:
            Path to the generated PNG file
        """
        # Calculate distance between user and aircraft
        user_location = (self.config.lat, self.config.lon)
        aircraft_location = (flight_details.latitude, flight_details.longitude)
        distance_km = geodesic(user_location, aircraft_location).kilometers

        # Determine zoom level based on distance
        if distance_km < 5:
            zoom_start = 14
        elif distance_km < 20:
            zoom_start = 11
        elif distance_km < 50:
            zoom_start = 9
        else:
            zoom_start = 7

        # Create the map centered between user and aircraft
        center_lat = (self.config.lat + flight_details.latitude) / 2
        center_lon = (self.config.lon + flight_details.longitude) / 2

        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, height=600, width=1200)

        # Add user location marker (red)
        folium.Marker(
            location=[self.config.lat, self.config.lon],
            popup="Your Location",
            icon=folium.Icon(color='red', icon='home')
        ).add_to(m)

        # Add aircraft location marker (blue)
        folium.Marker(
            location=[flight_details.latitude, flight_details.longitude],
            popup=f"{flight_details.flight_number}<br>{flight_details.route_code}<br>{distance_km:.1f} km away",
            icon=folium.Icon(color='blue', icon='plane')
        ).add_to(m)

        # Fit bounds with reduced padding for narrower viewport
        bounds = [
            [self.config.lat, self.config.lon],
            [flight_details.latitude, flight_details.longitude]
        ]
        m.fit_bounds(bounds, padding=(20, 20), max_zoom=zoom_start)

        # Save as HTML first, then convert to PNG using Selenium
        html_path = os.path.join(self.config.log_dir, 'flight_map.html')
        png_path = os.path.join(self.config.log_dir, 'flight_map.png')

        m.save(html_path)

        # Convert HTML to PNG using Selenium with headless Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1200,600')

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            driver.get(f'file://{os.path.abspath(html_path)}')
            time.sleep(3)  # Wait for map to fully render
            driver.save_screenshot(png_path)
        finally:
            driver.quit()

        logger.info(f"Map saved to {png_path}")
        return png_path

    
    def send_discord_notification(self, text_header: str, text_message: str, map_path: str) -> bool:
        """Send notification to Discord webhook. Returns True if successful."""
        if not self.config.webhook_url:
            logger.warning("Discord webhook not configured, skipping notification")
            return False

        try:
            webhook = DiscordWebhook(url=self.config.webhook_url)

            with open(map_path, "rb") as f:
                webhook.add_file(file=f.read(), filename=map_path)

            embed = DiscordEmbed(title=text_header, description=text_message)
            embed.set_image(url=f"attachment://{map_path}")
            webhook.add_embed(embed)
            response = webhook.execute()

            if response.status_code == 200:
                logger.info("Discord notification sent successfully")
                return True
            else:
                logger.error(f"Discord notification failed (status {response.status_code})")
                return False
        except Exception as e:
            logger.error(f"Discord notification error: {e}")
            return False


def get_timezone(latitude: float, longitude: float) -> str:
    """Get timezone string from coordinates."""
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
    if timezone_str is None:
        timezone_str = "Asia/Hong_Kong"
    return timezone_str

if __name__ == "__main__":
    tracker = FlightTracker()
    tracker.run()

    # TODO:
    # - Dockerize for deployment on remote server
    # - Selenium required for server
