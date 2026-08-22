#!/bin/bash
# Lance le pipeline complet (scrape -> analyse -> dashboard) depuis cron/systemd.
# Si la session en cache a expiré, fetch_scraper.py s'arrête proprement avec un message
# clair au lieu de planter (pas de Selenium/navigateur installé sur ce board).
set -euo pipefail

APP_DIR="$HOME/strava_export"
cd "$APP_DIR"
source .venv/bin/activate

export DASHBOARD_OUTPUT_PATH="/var/www/html/strava_dashboard.html"
export PYTHONUTF8=1

python3 fetch_scraper.py
python3 analyse.py
python3 generate_site.py
