#!/bin/bash
# Mise en place initiale sur le Tinkerboard (DietPi, ARM 32-bit, headless).
# Ne nécessite NI Selenium NI Chromium : le board ne fait que rejouer une session
# Strava déjà authentifiée (voir README pour le renouvellement de session).
set -euo pipefail

REPO_URL="https://github.com/pabecq/strava_export.git"
APP_DIR="$HOME/strava_export"

if [ ! -d "$APP_DIR" ]; then
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install --no-cache-dir -r requirements-board.txt

mkdir -p logs output
chmod +x deploy/run_pipeline.sh

# Secret partagé entre le bookmarklet (save_session.php) et generate_site.py, pour que
# n'importe qui sur le réseau ne puisse pas écraser la session en cache.
SECRET_FILE="$APP_DIR/output/.session_secret"
if [ ! -f "$SECRET_FILE" ]; then
    head -c 32 /dev/urandom | sha256sum | cut -d' ' -f1 > "$SECRET_FILE"
fi

# Cron toutes les 4h : scrape -> analyse -> dashboard. On évite les doublons si le
# script est relancé plusieurs fois.
CRON_CMD="0 */4 * * * $APP_DIR/deploy/run_pipeline.sh >> $APP_DIR/logs/cron.log 2>&1"
( crontab -l 2>/dev/null | grep -vF "run_pipeline.sh" ; echo "$CRON_CMD" ) | crontab -

echo ""
echo ">>> Dépôt prêt dans $APP_DIR"
echo ">>> Il manque encore un seul fichier, à copier depuis ta machine (celle avec un navigateur) :"
echo "      output/strava_session.json     (généré par 'python fetch_scraper.py --manual-login')"
echo ""
echo "   .env n'est PAS nécessaire ici : ce board ne se connecte jamais lui-même à Strava,"
echo "   il ne fait que rejouer la session déjà authentifiée."
echo ""
echo "   Exemple depuis ta machine :"
echo "      scp output/strava_session.json dietpi@<IP_DU_BOARD>:$APP_DIR/output/"
echo ""
echo ">>> Cron installé : le pipeline tourne toutes les 4h (voir 'crontab -l')."
echo ">>> Dashboard écrit dans /var/www/html/strava_dashboard.html (installe un serveur web + PHP"
echo "    via 'dietpi-software' si ce n'est pas déjà fait, ex: nginx+php-fpm ou lighttpd+php)."
echo ""
echo ">>> Pour le bouton 'Reconnecter Strava' en un clic (bookmarklet) :"
echo "    1. Copie les endpoints PHP dans le document root du serveur web :"
echo "         sudo cp $APP_DIR/web/*.php /var/www/html/"
echo "    2. Autorise le serveur web (souvent l'utilisateur www-data) à écrire la session"
echo "       et à exécuter le pipeline :"
echo "         sudo usermod -aG dietpi www-data"
echo "         chmod -R g+rwX $APP_DIR/output $APP_DIR/logs"
echo "         chmod g+rx $APP_DIR $APP_DIR/deploy"
echo "         sudo systemctl restart php*-fpm 2>/dev/null || true"
echo "    3. Configure DASHBOARD_BASE_URL pour que le lien du bookmarklet soit généré :"
echo "         cp $APP_DIR/deploy/board.env.example $APP_DIR/deploy/board.env"
echo "         puis édite deploy/board.env avec l'IP réelle du board (ex: http://192.168.1.42)"
echo ""
echo "    Secret de session (déjà généré, ne pas partager) : $(cat "$SECRET_FILE")"
