#!/usr/bin/env python3
import os
import time
import json
import random
import logging
import pandas as pd
import requests
from pathlib import Path
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import sys

try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"
ENV_FILE = BASE_DIR / ".env"
DATA_FILE = OUTPUT_DIR / 'raw_strava_data.csv'
SESSION_FILE = OUTPUT_DIR / 'strava_session.json'

LOG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "strava_scraper.log"),
        logging.StreamHandler()
    ]
)

load_dotenv(ENV_FILE)
STRAVA_EMAIL = os.getenv("STRAVA_EMAIL")
STRAVA_PASSWORD = os.getenv("STRAVA_PASSWORD")

if not STRAVA_EMAIL or not STRAVA_PASSWORD:
    logging.error("❌ Identifiants Strava absents du fichier .env")
    exit(1)

def get_chrome_major_version():
    """Détecte la version majeure du Chrome installé, pour que undetected-chromedriver
    télécharge un chromedriver compatible (son auto-détection peut se tromper)."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                import win32api
                version = win32api.GetFileVersionInfo(path, "\\")
                ms = version["FileVersionMS"]
                return win32api.HIWORD(ms)
            except ImportError:
                # Pas de pywin32 : on lit le dossier de version installée à côté du binaire
                app_dir = Path(path).parent
                versions = [d.name for d in app_dir.iterdir() if d.is_dir() and d.name[0].isdigit()]
                if versions:
                    return int(sorted(versions, reverse=True)[0].split('.')[0])
    return None


def create_driver():
    """Crée le driver Chrome. Utilise undetected-chromedriver quand disponible
    (hors Docker/Linux, où l'on reste sur Chromium + chromedriver standard)."""
    if sys.platform == "linux":
        options = Options()
        options.add_argument("--window-size=1920,1080")
        options.binary_location = "/usr/bin/chromium"

        # Revert to standard headless. Debian's Chromium version might not support '=new' yet.
        options.add_argument("--headless")

        # Core Docker fixes
        options.add_argument("--no-sandbox") # Crucial for running as root in Docker
        options.add_argument("--disable-dev-shm-usage") # Overcomes limited RAM in Docker

        # Additional stability flags for containerized environments
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-setuid-sandbox")

        # --- OPTIONS ANTI-BOT ---
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        service = Service("/usr/bin/chromedriver")
        return webdriver.Chrome(service=service, options=options)

    if HAS_UC:
        # undetected-chromedriver patche le driver pour contourner les détections
        # classiques (navigator.webdriver, etc.) qui alimentent le score reCAPTCHA.
        # version_main est forcé pour éviter un mismatch si l'auto-détection récupère
        # une version de chromedriver plus récente que le Chrome réellement installé.
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1920,1080")
        return uc.Chrome(options=options, version_main=get_chrome_major_version())

    options = Options()
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


def human_type(element, text):
    """Tape caractère par caractère avec un délai aléatoire, pour éviter la signature
    'collée en un seul bloc' d'un send_keys() classique."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.18))


def load_cached_session():
    """Charge une session (cookies + csrf) précédemment sauvegardée, si elle existe."""
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_cached_session(cookies, csrf_token):
    SESSION_FILE.write_text(
        json.dumps({"cookies": cookies, "csrf_token": csrf_token}),
        encoding="utf-8"
    )


def build_scraping_session(cookies, csrf_token):
    """Construit la session Requests utilisée pour appeler l'API interne Strava."""
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "X-CSRF-Token": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "Referer": "https://www.strava.com/athlete/training"
    })
    return session


def try_cached_session():
    """Tente de réutiliser la session sauvegardée pour éviter un login Selenium
    (moins de logins = moins de risque de déclencher la détection anti-bot)."""
    cached = load_cached_session()
    if not cached:
        return None

    session = build_scraping_session(cached["cookies"], cached["csrf_token"])
    try:
        r = session.get(
            "https://www.strava.com/athlete/training_activities",
            params={"new_activity_only": "false", "page": 1, "perPage": 1},
            timeout=10
        )
        if r.ok and "models" in r.json():
            logging.info("♻️  Session Strava réutilisée depuis le cache (pas de login Selenium nécessaire).")
            return session
    except Exception:
        pass

    logging.info("   Session en cache invalide/expirée, nouveau login Selenium requis.")
    return None


def get_strava_session():
    """Utilise Selenium pour se connecter et récupérer les cookies + le token CSRF"""
    driver = create_driver()

    try:
        logging.info("🚀 Lancement de Selenium pour l'authentification...")
        driver.get("https://www.strava.com/login")
        wait = WebDriverWait(driver, 15)

        # 1. Accepter les cookies (souvent requis en Europe pour débloquer la page)
        try:
            cookie_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accepter') or contains(text(), 'Accept')]"))
            )
            cookie_btn.click()
            time.sleep(1)
        except:
            pass # Pas de bandeau cookie, on continue

        # 2. ÉTAPE 1 : L'email
        logging.info("   -> Saisie de l'email...")
        # On cherche par 'name="email"' car c'est commun aux versions desktop et mobile
        email_field = wait.until(EC.presence_of_element_located((By.ID, "desktop-email")))
        time.sleep(1)
        human_type(email_field, STRAVA_EMAIL)
        time.sleep(1)
        email_field.send_keys(Keys.RETURN) # Taper "Entrée" soumet l'étape 1

        # Petite pause pour laisser l'animation JS afficher le champ du mot de passe
        time.sleep(2) 

        # --- NOUVELLE ÉTAPE : Contourner la 2FA (OTP) ---
        logging.info("   -> Recherche du lien 'Use password instead' / 'Utiliser plutot un mot de passe'...")
        try:
            time.sleep(1)

            # On cherche par le texte (FR + EN, car Strava affiche la page selon la langue du navigateur).
            # Strava rend ce bouton en double dans le DOM (layout desktop + mobile/tablette caché),
            # donc on filtre sur l'élément réellement visible plutôt que de prendre le premier trouvé.
            candidates = driver.find_elements(
                By.XPATH,
                "//button[contains(., 'Use password instead') or "
                "contains(., 'Utiliser plutôt un mot de passe')]"
            )
            visible_candidates = [c for c in candidates if c.is_displayed()]
            if not visible_candidates:
                raise NoSuchElementException("No visible 'use password instead' button")

            otp_bypass_btn = wait.until(EC.element_to_be_clickable(visible_candidates[0]))
            otp_bypass_btn.click()
            logging.info("   -> Clic réussi, on passe au mot de passe classique.")
            time.sleep(2) # Pause pour laisser l'animation afficher le champ de mot de passe
        except Exception:
            # On met un try/except car parfois Strava ne demande pas la 2FA (selon l'IP/historique)
            logging.info("   -> Pas de demande 2FA détectée, on continue...")

        # 3. ÉTAPE 3 : Le mot de passe
        # Même souci de duplication desktop/mobile que pour le bouton OTP : on filtre sur le champ visible.
        logging.info("   -> Saisie du mot de passe...")
        wait.until(lambda d: any(e.is_displayed() for e in d.find_elements(By.NAME, "password")))
        pwd_field = next(e for e in driver.find_elements(By.NAME, "password") if e.is_displayed())
        human_type(pwd_field, STRAVA_PASSWORD)
        pwd_field.send_keys(Keys.RETURN) # Taper "Entrée" soumet la connexion finale

        # 4. Attendre d'être connecté (présence de la barre de navigation du dashboard)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "global-nav")))
        logging.info("✅ Connexion réussie.")

        # Récupération des cookies
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}

        # Récupération du Token CSRF caché dans le HTML de la page connectée
        csrf_token = driver.execute_script("return document.querySelector('meta[name=\"csrf-token\"]').content;")

        save_cached_session(cookies, csrf_token)
        return cookies, csrf_token

    except Exception as e:
        logging.error(f"❌ Erreur lors de la connexion Selenium : {e}")
        # Capture d'écran très utile en cas de plantage pour comprendre ce que voit le robot
        driver.save_screenshot(str(LOG_DIR / "crash_strava_login.png"))
        raise
    finally:
        driver.quit()

def main():
    # 1. Réutiliser une session en cache si possible, sinon se logger via Selenium
    session = try_cached_session()
    if session is None:
        cookies, csrf_token = get_strava_session()
        session = build_scraping_session(cookies, csrf_token)

    url = "https://www.strava.com/athlete/training_activities"
    all_activities = []
    page = 1
    per_page = 50

    logging.info("🌍 Début du téléchargement des activités via l'API interne...")

    while True:
        params = {
            "new_activity_only": "false",
            "page": page,
            "perPage": per_page
        }

        r = session.get(url, params=params)
        r.raise_for_status()

        data = r.json()
        activities = data.get("models", [])
        
        if not activities:
            break
            
        all_activities.extend(activities)
        total_expected = data.get("total", "???")
        
        logging.info(f"   ⬇️ Page {page} récupérée ({len(activities)} act.). Total provisoire : {len(all_activities)}/{total_expected}")
        
        page += 1
        time.sleep(1) # Sécurité anti-ban

    if not all_activities:
        logging.warning("⚠️ Aucune activité trouvée.")
        return

    # 3. Sauvegarde et mise en forme
    df = pd.DataFrame(all_activities)
    
    df = df.rename(columns={
        "start_time": "start_date_local",
        "distance_raw": "distance",
        "moving_time_raw": "moving_time",
        "elapsed_time_raw": "elapsed_time",
        "elevation_gain_raw": "total_elevation_gain",
    })

    if 'start_date_local' in df.columns:
        df['start_date_local'] = pd.to_datetime(df['start_date_local'])
        df.sort_values(by='start_date_local', ascending=False, inplace=True)

    df.to_csv(DATA_FILE, index=False)
    logging.info(f"💾 SUCCESS. {len(df)} activités sauvegardées dans {DATA_FILE}")

if __name__ == "__main__":
    main()