import os
import requests
import pandas as pd
import logging
from dotenv import load_dotenv
from pathlib import Path
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

### CONFIGURATION ###

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / 'logs'
OUTPUT_DIR = BASE_DIR / 'output'
ENV_FILE = BASE_DIR / '.env'

LOG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    filename=LOG_DIR / "strava_export.log",
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console Handler (so you see logs in terminal)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

load_dotenv(ENV_FILE)
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    raise ValueError("❌ Missing credentials in .env file.")

### UTILS ###

def get_request_session():
    """Creates a session with retry logic for network stability."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def check_rate_limits(response):
    """Reads Strava headers and sleeps if we are close to the limit."""
    try:
        usage = response.headers.get('X-RateLimit-Usage', '0,0').split(',')
        limit = response.headers.get('X-RateLimit-Limit', '600,3000').split(',')
        
        # 15-min limit check (first number)
        usage_15m = int(usage[0])
        limit_15m = int(limit[0])
        
        if usage_15m >= (limit_15m * 0.90): # 90% capacity
            logging.warning(f"⚠️ Rate limit approaching ({usage_15m}/{limit_15m}). Pausing for 60s...")
            time.sleep(60)
    except Exception:
        pass # Don't crash on header parsing errors

### MAIN PROCESS ###

def main():
    session = get_request_session()
    
    # 1. Get Access Token
    url_token = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token',
        'f': 'json'
    }

    logging.info("🔄 Refreshing access token...")
    try:
        res = session.post(url_token, data=payload)
        res.raise_for_status()
        access_token = res.json()['access_token']
        logging.info("✅ Token refreshed.")
    except Exception as e:
        logging.error(f"❌ Auth failed: {e}")
        return

    # 2. Fetch Activities
    url_act = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f"Bearer {access_token}"}
    
    all_activities = []
    page = 1
    
    logging.info("🚀 Starting activity fetch...")

    while True:
        params = {'per_page': 200, 'page': page}
        
        try:
            r = session.get(url_act, headers=headers, params=params)
            check_rate_limits(r)
            r.raise_for_status()
            
            data = r.json()
            
            if not data:
                break
            
            all_activities.extend(data)
            logging.info(f"   -> Page {page}: {len(data)} activities fetched. (Total: {len(all_activities)})")
            page += 1
            
        except Exception as e:
            logging.error(f"❌ Error on page {page}: {e}")
            logging.info("⚠️ Saving partial data and stopping.")
            break

    # 3. Save Data
    if all_activities:
        df = pd.DataFrame(all_activities)
        csv_path = OUTPUT_DIR / "raw_strava_data.csv"
        df.to_csv(csv_path, index=False, sep=",")
        logging.info(f"💾 SUCCESS: {len(df)} activities saved to {csv_path}")
    else:
        logging.warning("⚠️ No activities found or fetch failed completely.")

if __name__ == "__main__":
    main()