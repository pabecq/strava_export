import os
import requests
import pandas as pd
import logging
from dotenv import load_dotenv
from pathlib import Path
import time


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
    format='%(asctime)s - %(levelname)s - %(message)s'
)

#Importe MDP et IDs depuis .env
load_dotenv(ENV_FILE)
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")


### RECUPERATION DU TOKEN ###
url_token = "https://www.strava.com/oauth/token"

payload = {
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'refresh_token': REFRESH_TOKEN,
    'grant_type': 'refresh_token',
    'f': 'json'
}

logging.info("Demande d'un nouveau token d'accès...")
res = requests.post(url_token, data=payload, verify=False) 

access_token = res.json()['access_token']
logging.info("Nouveau token reçu.")

### RECUPERATION DES ACTIVITEs ###

url_act = "https://www.strava.com/api/v3/athlete/activities"
headers = {'Authorization': f"Bearer {access_token}"}

all_activities = []
page = 1

while True:
    logging.info(f'Recuperation de la page: {page}')
    params = {'per_page': 200, 'page': page}

    r = requests.get(url_act, headers=headers, params=params)
    r.raise_for_status()        
    data = r.json()

    if not data:
            break # Plus d'activités, on arrête
    
    all_activities.extend(data)
    logging.info(f"{len(data)} activités trouvées sur cette page.")
    page += 1
    time.sleep(1)


df = pd.DataFrame(all_activities)

# 5. Sauvegarde finale
csv_path = OUTPUT_DIR / "raw_strava_data.csv"
df.to_csv(csv_path, index=False, sep=",")
    
logging.info(f"SUCCÈS ! Fichier sauvegardé : {csv_path}")
print(f"🎉 Terminé ! Fichier sauvegardé : {csv_path}")
