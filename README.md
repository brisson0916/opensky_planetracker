# OpenSky Flight Tracker: Your Personal Flight Radar with Discord Alerts

Ever wondered what planes are flying overhead right now? 

The OpenSky Flight Tracker monitors airspace around your location using the OpenSky Network API and sends real-time Discord notifications whenever a flight passes by.

It includes flight route, altitude, velocity, and a map screenshot pinpointing the aircraft, just like the screenshot below:
![Alt text](./media/sample_screenshot.png)

## Features

- Fetches closest airborne flight to your location within a configurable radius
- Real-time flight data about flight route, altitude, velocity, direction, etc.
- Generates a static map image
- Sends Discord webhook notifications with flight details
- Does not duplicate notifications for same flight within configurable time frame
- Automated scheduling with cron (supports up to every 30 seconds)

## Dependencies

| Package | Purpose |
|---------|---------|
| `selenium` | Browser automation for map screenshots |
| `webdriver-manager` | Auto-installs chromedriver |
| `folium` | Map generation |
| `geopy` | Distance calculations |
| `requests` | OpenSky & ADSBDB API calls |
| `discord-webhook` | Discord notifications |
| `timezonefinder` | Timezone lookup |
| `python-dotenv` | Environment variable loading |


## Project Structure

```
opensky_planetracker/
├── main.py           # Main entry point
├── config.py         # Configuration (location, radius, etc.)
├── models.py         # Data models and formatting
├── .env              # Environment variables (credentials)
├── .venv/            # Virtual environment (created by uv)
├── logs/             # Runtime logs
│   ├── flight_tracker.log
│   └── spotted_planes.json  # Deduplication cache
└── pyproject.toml    # Dependencies
```

## Prerequisites

- Python 3.14+
- **Chrome** or **Chromium** installed (required for Selenium map generation)
- `chromedriver` compatible with your Chrome version (auto-installed by webdriver-manager)

### Installing Chrome on Linux

```bash

# Ubuntu/Debian
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update && sudo apt install -y google-chrome-stable
```

### Installing Chrome on Mac

```bash
brew install --cask google-chrome
```

## Getting Your OpenSky API Keys

The OpenSky Network uses OAuth2 client credentials for authentication. Follow these steps to get your `CLIENT_ID` and `CLIENT_SECRET`:

**1. Create an OpenSky account**

Sign up at [opensky-network.org](https://opensky-network.org) if you don't have one.

**2. Go to your Account page**

Once logged in, navigate to your account page.

**3. Create an API client**

Look for the **API clients** section and create a new client. This will generate a `client_id` and `client_secret` for you.

**4. Copy the credentials**

Your credentials will look something like:
- `CLIENT_ID`: `your-email-api-client`
- `CLIENT_SECRET`: `a1b2c3d4e5f6...`

> Note: Tokens expire after 30 minutes. The script automatically refreshes them, so you just need the initial credentials.

---

## Setting Up a Discord Webhook

Discord webhooks let this script send notifications to a channel.

**1. Create a Discord channel** (or use an existing one)

The channel must be in a server where you have the **Manage Webhooks** permission.

**2. Create a webhook for that channel**

- Click the channel name → **Edit Channel**
- Go to **Integrations → Webhooks**
- Click **Create Webhook**
- Name it (e.g., "Flight Tracker") and click **Copy Webhook URL**

The URL will look like:
```
https://discord.com/api/webhooks/1234567890/abcdefghijklmnop
```

**3. Use the full webhook URL in your `.env` file**

Assign the entire URL to `WEBHOOK_URL`.

## Setting up the Python Environment and Script

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd opensky_planetracker
```

### 2. Create and activate a virtual environment with uv

```bash
uv venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
uv sync
```

This installs all packages including `selenium`, `webdriver-manager`, `folium`, `geopy`, etc.

### 4. Configure environment variables

Create an `.env` file and edit it as below:

```bash
CLIENT_ID="your-opensky-client-id"
CLIENT_SECRET="your-opensky-client-secret"
WEBHOOK_URL="https://discord.com/api/webhooks/..."
MY_LAT="xxx.xxx"        # Your latitude
MY_LON="yyy.yyy"       # Your longitude
RADIUS_KM="5"           # Search radius for nearby flights (KM)
```

### 5. Test the script

```bash
uv run python main.py
```

You should see output like:

```
Plane Spotted 3.7km away! (2026-03-31 16:47:17+08:00) 
Flight: UO851
Route: KIX-HKG
State of Registry: China
Altitude: 906.8 meters
Velocity: 299.9 km/h (heading S 70.9° W)
Climb Rate: -6.5 m/s

This is Hong Kong Express Airways's flight UO851 from Osaka, Japan to Hong Kong, Hong Kong.
Track it: https://www.flightradar24.com/HKE851  
```

And a Discord notification with a map.

---

## Running on a Schedule with Cron (MacOS/Linux)

**1. Open the crontab editor:**

```bash
crontab -e
```

**2. Add one of the following configurations:**

**Every minute:**
```cron
* * * * * cd "/full/path/to/opensky_planetracker" && /full/path/to/uv run python main.py
```

**Every 30 seconds** (two entries):
```cron
* * * * * cd "/full/path/to/opensky_planetracker" && /full/path/to/uv run python main.py
* * * * * sleep 30 && cd "/full/path/to/opensky_planetracker" && /full/path/to/uv run python main.py
```

> **Important:**
> - Use absolute paths. Cron runs with a minimal environment and won't find `uv` or relative paths.
> - Run `which uv` in terminal to get the full path to `uv` (e.g., `/opt/homebrew/bin/uv`).
> - Paths with spaces must be quoted.

**3. Verify your crontab:**

```bash
crontab -l
```

### Note

Be aware that **macOS may require additional permissions** for cron to run scripts.

To grant cron Full Disk Access:
1. Go to **System Settings → Privacy & Security → Full Disk Access**
2. Add `/usr/sbin/cron` to the list

Or alternatively, use `launchd` as a more macOS-native scheduler.

---