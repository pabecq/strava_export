import os
import time
import logging
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / 'logs'
OUTPUT_DIR = BASE_DIR / 'output'
ENV_FILE = BASE_DIR / '.env'
DATA_FILE = OUTPUT_DIR / 'raw_strava_data.csv'

# Setup Logging
LOG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "strava_export.log"),
        logging.StreamHandler()
    ]
)

# Load Credentials
load_dotenv(ENV_FILE)
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    logging.error("❌ Missing credentials. Check your .env file.")
    exit(1)

# --- UTILS ---

def get_session():
    """Creates a requests session with retry logic."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def refresh_access_token(session):
    """Exchanges the refresh token for a new access token."""
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token',
        'f': 'json'
    }
    try:
        res = session.post(url, data=payload)
        res.raise_for_status()
        logging.info("🔐 Access Token Refreshed")
        return res.json()['access_token']
    except Exception as e:
        logging.error(f"❌ Auth failed: {e}")
        exit(1)

def check_rate_limits(response):
    """Monitors Strava rate limits and pauses if necessary."""
    try:
        usage = response.headers.get('X-RateLimit-Usage', '0,0').split(',')
        limit = response.headers.get('X-RateLimit-Limit', '600,3000').split(',')
        
        # Check 15-minute limit (index 0)
        usage_15m = int(usage[0])
        limit_15m = int(limit[0])
        
        if usage_15m >= (limit_15m * 0.9):
            logging.warning(f"⚠️ Rate limit critical ({usage_15m}/{limit_15m}). Pausing for 60s...")
            time.sleep(60)
    except:
        pass

def get_last_sync_timestamp():
    """Reads existing CSV to find the latest activity timestamp."""
    if not DATA_FILE.exists():
        return None
    
    try:
        # Read only necessary columns to be fast
        df = pd.read_csv(DATA_FILE, usecols=['start_date'])
        if df.empty:
            return None
        
        df['start_date'] = pd.to_datetime(df['start_date'])
        last_date = df['start_date'].max()
        
        # Return epoch timestamp + 1 second to avoid overlap
        return int(last_date.timestamp()) + 1
    except Exception as e:
        logging.warning(f"⚠️ Could not read last date ({e}). Doing full fetch.")
        return None

# --- MAIN LOGIC ---

def main():
    session = get_session()
    access_token = refresh_access_token(session)
    
    # 1. Determine where to start
    start_timestamp = get_last_sync_timestamp()
    if start_timestamp:
        logging.info(f"📅 Incremental sync: Fetching activities after timestamp {start_timestamp}")
    else:
        logging.info("🌍 Full history sync started.")

    # 2. Fetch Data
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f"Bearer {access_token}"}
    
    new_activities = []
    page = 1
    
    while True:
        params = {'per_page': 200, 'page': page}
        if start_timestamp:
            params['after'] = start_timestamp
            
        try:
            r = session.get(url, headers=headers, params=params)
            check_rate_limits(r)
            r.raise_for_status()
            
            data = r.json()
            
            if not data:
                break
                
            new_activities.extend(data)
            logging.info(f"   ⬇️ Page {page}: Retrieved {len(data)} activities.")
            page += 1
            
        except Exception as e:
            logging.error(f"❌ Error fetching page {page}: {e}")
            break

    # 3. Merge and Save
    if not new_activities:
        logging.info("✅ No new activities found. You are up to date.")
        return

    df_new = pd.DataFrame(new_activities)
    
    if DATA_FILE.exists():
        try:
            logging.info("🔄 Merging with existing database...")
            df_old = pd.read_csv(DATA_FILE)
            
            # Concatenate
            df_combined = pd.concat([df_old, df_new])
            
            # Deduplicate based on ID (keep the new one if conflict)
            initial_len = len(df_combined)
            df_combined = df_combined.drop_duplicates(subset=['id'], keep='last')
            
            logging.info(f"   Added {len(df_new)} new. Total: {len(df_combined)} activities.")
        except Exception as e:
            logging.error(f"❌ Error merging data: {e}")
            return
    else:
        df_combined = df_new
        logging.info(f"   Created new database with {len(df_combined)} activities.")

    # Sort by date (descending)
    if 'start_date' in df_combined.columns:
        df_combined.sort_values(by='start_date', ascending=False, inplace=True)

    # Atomic Save (Write to temp, then rename) to prevent corruption
    temp_file = OUTPUT_DIR / "raw_strava_data_temp.csv"
    df_combined.to_csv(temp_file, index=False)
    temp_file.replace(DATA_FILE)
    
    logging.info(f"💾 SUCCESS. Database saved to {DATA_FILE}")

if __name__ == "__main__":
    main()