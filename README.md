# 🏃‍♂️ Performance Lab — Strava Analytics Dashboard

> Pipeline de données complet et tableau de bord personnel pour analyser vos données d'entraînement Strava avec des modèles physiologiques avancés.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)
![Strava](https://img.shields.io/badge/Strava-API%20v3-FC4C02?style=flat-square&logo=strava&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-Interactive-3F4F75?style=flat-square&logo=plotly&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-7952B3?style=flat-square&logo=bootstrap&logoColor=white)

---

## 📖 Présentation

**Performance Lab** va au-delà des simples statistiques de distance et de temps. En s'appuyant sur des modèles physiologiques reconnus — **Modèle de Banister**, **Seuil Lactique (LTHR)**, **TRIMP** — il vous offre une vision complète et scientifique de votre progression :

- Suivre votre **condition physique** (CTL/Fitness) et votre **fatigue** (ATL)
- Prédire votre **état de forme** (TSB) avant une compétition
- Classifier vos efforts par **zones d'intensité** basées sur votre seuil lactique

---

## ✨ Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| 🔄 **Sync intelligente** | Extraction incrémentale depuis l'API Strava avec gestion automatique des rate limits et renouvellement des tokens |
| 🧬 **Modèle de Banister** | Calcul continu du CTL (Fitness), ATL (Fatigue) et TSB (Forme) |
| ⚡ **TRIMP** | Calcul de la charge d'entraînement, avec pondération automatique pour les séances sans capteur cardiaque |
| 🎯 **Zones LTHR** | Classification des efforts selon votre seuil lactique (méthode Friel / Coggan) |
| 📊 **Dashboard interactif** | Fichier HTML statique avec graphiques Plotly, suivi d'efficience (EF) et récapitulatif multi-sports |
| 🏊 **Multi-sports** | Supporte Course à pied, Vélo, Natation et Musculation |

---

## 📂 Structure du projet

```
pabecq-strava_export/
├── .env.example          # Modèle pour les variables d'environnement
├── requirements.txt      # Dépendances Python
├── fetch.py              # Extraction des activités depuis l'API Strava
├── analyse.py            # Moteur d'analyse physiologique (CTL, ATL, TSB, TRIMP...)
└── generate_site.py      # Générateur du tableau de bord HTML
```

---

## 🚀 Installation

### Prérequis

- **Python 3.8+**
- Un compte [Strava](https://www.strava.com/) avec des activités enregistrées
- Une application créée sur [Strava Developers](https://developers.strava.com/) pour obtenir vos clés d'API

### 1. Cloner et installer

```bash
git clone <votre-repo-url>
cd pabecq-strava_export
pip install -r requirements.txt
```

### 2. Configurer l'API Strava

```bash
cp .env.example .env
```

Éditez `.env` avec vos identifiants Strava :

```ini
STRAVA_CLIENT_ID=votre_client_id
STRAVA_CLIENT_SECRET=votre_client_secret
STRAVA_REFRESH_TOKEN=votre_refresh_token
```

> **Où trouver ces valeurs ?** Rendez-vous sur [strava.com/settings/api](https://www.strava.com/settings/api) après avoir créé votre application.

### 3. Personnaliser votre profil physiologique

Ouvrez `analyse.py` et modifiez le dictionnaire `PHYSIO` en haut du fichier avec vos propres données :

```python
PHYSIO = {
    "hr_max": 190,        # Fréquence cardiaque maximale
    "hr_rest": 45,        # Fréquence cardiaque au repos
    "hr_lthr": 168,       # Fréquence cardiaque au seuil lactique (LTHR)
    # ...
}
```

Ces valeurs sont essentielles pour la précision des calculs de zones et de charge d'entraînement.

---

## ⚙️ Utilisation

Le pipeline s'exécute en 3 étapes séquentielles :

```bash
# Étape 1 — Récupérer les nouvelles activités depuis Strava
python fetch.py

# Étape 2 — Calculer les métriques physiologiques (CTL, ATL, TSB, TRIMP...)
python analyse.py

# Étape 3 — Générer le tableau de bord HTML
python generate_site.py
```

Le dashboard est généré par défaut dans `/var/www/html/strava_dashboard.html`. Ce chemin est configurable directement dans `generate_site.py`.

---

## 📊 Modèles physiologiques utilisés

### Modèle de Banister (Impulse-Response)
Le modèle décompose la performance en trois composantes calculées quotidiennement :
- **CTL** (Chronic Training Load) — Fitness chronique, moyenne longue (~42 jours)
- **ATL** (Acute Training Load) — Fatigue aiguë, moyenne courte (~7 jours)
- **TSB** (Training Stress Balance) — Forme du jour : `TSB = CTL - ATL`

### TRIMP (Training Impulse)
Mesure de la charge d'entraînement pondérée par la fréquence cardiaque. Pour les séances sans capteur, la charge est estimée à partir de la vitesse au seuil.

### Zones d'intensité LTHR (Friel / Coggan)
Les efforts sont classifiés en zones basées sur votre **seuil lactique** plutôt que sur la FC maximale, pour une répartition plus précise et personnalisée.

---

## 🛠️ Stack technique

- **Python** — Logique principale du pipeline
- **Pandas & NumPy** — Manipulation et calcul vectoriel des données
- **Plotly** — Visualisations interactives embarquées
- **Bootstrap 5** — Interface et composants du dashboard HTML
- **API Strava v3** — Source des données d'entraînement

---

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une *issue* pour signaler un bug ou proposer une amélioration, ou à soumettre une *pull request*.

---

## 📄 Licence

Ce projet est distribué sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.
