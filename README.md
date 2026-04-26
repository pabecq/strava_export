🏃‍♂️ Performance Lab - Strava Analytics Dashboard

Performance Lab est un pipeline de données complet et un tableau de bord personnel conçu pour extraire, analyser et visualiser vos données d'entraînement depuis l'API Strava.

Il va au-delà des simples statistiques de distance et de temps en intégrant des modèles physiologiques avancés (Modèle de Banister, Seuil Lactique LTHR, TRIMP) pour vous aider à suivre votre condition physique (Fitness), votre fatigue et prédire votre état de forme.

✨ Fonctionnalités

🔄 Synchronisation intelligente : Extraction incrémentale depuis l'API Strava avec gestion automatique des limites de requêtes (rate limits) et des jetons d'accès.

🧬 Modélisation Physiologique : * Calcul de la charge d'entraînement (TRIMP).

Gestion continue du modèle de Banister : CTL (Fitness), ATL (Fatigue) et TSB (Forme).

Pondération automatique de la charge pour les séances sans capteur cardiaque en fonction de votre vitesse au seuil.

🎯 Zones d'intensité LTHR : Classification des efforts basée sur votre Seuil Lactique (Friel / Coggan) plutôt que sur la FC Max.

📊 Dashboard Interactif : Génération d'un fichier HTML statique intégrant des graphiques interactifs (Plotly), un suivi d'efficience (EF), un récapitulatif multi-sports (Course, Vélo, Natation, Musculation) et le détail de vos dernières activités.

📂 Structure du Projet

└── pabecq-strava_export/
    ├── .env.example       # Modèle pour les clés d'API Strava
    ├── requirements.txt   # Dépendances Python
    ├── fetch.py           # Script d'extraction des données Strava
    ├── analyse.py         # Moteur d'analyse physiologique
    └── generate_site.py   # Générateur du Dashboard HTML


🚀 Installation & Configuration

1. Prérequis

Python 3.8+

Une application créée sur Strava Developers pour obtenir vos clés d'API.

2. Cloner le projet et installer les dépendances

git clone <votre-repo-url>
cd pabecq-strava_export
pip install -r requirements.txt


3. Configurer l'API Strava
Copiez le fichier .env.example vers .env et ajoutez vos identifiants :

cp .env.example .env


Éditez .env avec vos valeurs :

STRAVA_CLIENT_ID=votre_client_id
STRAVA_CLIENT_SECRET=votre_client_secret
STRAVA_REFRESH_TOKEN=votre_refresh_token


4. Personnaliser votre physiologie
Ouvrez le fichier analyse.py et modifiez le dictionnaire PHYSIO en haut du fichier avec vos propres données (Fréquence cardiaque max, au repos, au seuil lactique, etc.) pour des calculs précis.

⚙️ Utilisation

Le pipeline s'exécute en 3 étapes. Exécutez ces commandes dans l'ordre :

# 1. Récupérer les nouvelles activités depuis Strava
python fetch.py

# 2. Analyser les données et calculer les métriques (CTL, ATL, TSB...)
python analyse.py

# 3. Générer le fichier HTML du Dashboard
python generate_site.py


Le tableau de bord sera généré (par défaut configuré pour /var/www/html/strava_dashboard.html, modifiable dans generate_site.py) et prêt à être consulté dans votre navigateur web.

🛠️ Technologies Utilisées

Python (Logique principale)

Pandas & NumPy (Manipulation et calcul vectoriel de données)

Plotly (Visualisations interactives)

Bootstrap 5 (Interface UI / Composants HTML)

API Strava v3 (Source des données)
