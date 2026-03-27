# OpenSky Flight Tracker

Tracks nearby flights using the OpenSky Network API and sends Discord notifications with a map screenshot.

## Features

- Fetches real-time flight data within a configurable radius
- Calculates closest airborne flight to your location
- Generates a static map image using Selenium + headless Chrome
- Sends Discord webhook notifications with flight details
- Deduplicates notifications within a configurable TTL
- 29-second execution timeout for cron safety

## Prerequisites

- Python 3.14+
- **Chrome** or **Chromium** installed (required for Selenium map generation)
- `chromedriver` compatible with your Chrome version (auto-installed by webdriver-manager)

### Installing Chrome on Linux (EC2)

```bash
# Amazon Linux 2023 / RHEL
sudo dnf install -y google-chrome-stable

# Ubuntu/Debian
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update && sudo apt install -y google-chrome-stable
```

### Installing Chrome on Mac

```bash
brew install --cask google-chrome
```

---

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

Discord webhooks let this script send notifications to a channel without a bot.

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

---

## Setup

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

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
CLIENT_ID="your-opensky-client-id"
CLIENT_SECRET="your-opensky-client-secret"
WEBHOOK_URL="https://discord.com/api/webhooks/..."
MY_LAT="xxx.xxx"        # Your latitude
MY_LON="yyy.yyy"       # Your longitude
```

### 5. Test the script

```bash
uv run python main.py
```

You should see output like:

```
Flight: CPA472 | HKG → JFK | 285km away
```

And a Discord notification with a map.

---

## Running on a Schedule with Cron

### Linux / EC2

**1. Open the crontab editor:**

```bash
crontab -e
```

**2. Add the following line to run every minute:**

```cron
* * * * * /full/path/to/opensky_planetracker/.venv/bin/python /full/path/to/opensky_planetracker/main.py >> /full/path/to/opensky_planetracker/logs/cron.log 2>&1
```

> **Important:** Use absolute paths. Cron runs with a minimal environment and won't find `.venv/bin/python` or relative paths.

**3. Verify your crontab:**

```bash
crontab -l
```

### Mac

Same as Linux, but be aware that **macOS may require additional permissions** for cron to run scripts.

To grant cron Full Disk Access:
1. Go to **System Settings → Privacy & Security → Full Disk Access**
2. Add `/usr/sbin/cron` to the list

Or alternatively, use `launchd` as a more macOS-native scheduler.

---

## Cron Log Output

The `>>` redirects both stdout and stderr to `logs/cron.log`. To watch the log in real time during testing:

```bash
tail -f logs/cron.log
```

---

## Project Structure

```
opensky_planetracker/
├── main.py           # Main entry point
├── config.py         # Configuration (location, radius, etc.)
├── models.py         # Data models
├── .env              # Environment variables (credentials)
├── .venv/            # Virtual environment (created by uv)
├── logs/             # Runtime logs
│   ├── flight_tracker.log
│   └── spotted_planes.json  # Deduplication cache
└── pyproject.toml    # Dependencies
```

---

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

---

## Troubleshooting

### "Chrome not found" / Selenium error

Ensure Chrome is installed and `chromedriver` can be found. The script uses `webdriver-manager` to auto-install it, but Chrome itself must be on your system.

On headless Linux servers, the `--no-sandbox` and `--disable-dev-shm-usage` flags are enabled by default in the script.

### Cron not running

- Check cron is running: `sudo systemctl status cron` (Linux)
- Verify paths are absolute in crontab
- Check the log file for errors: `tail -f logs/cron.log`

### Script times out

The script has a 29-second timeout to prevent cron overlap. If your internet is slow, increase the timeout in `main.py` (`signal.alarm(29)`).
