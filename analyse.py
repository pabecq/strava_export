import pandas as pd
import numpy as np

df= pd.read_csv('output/raw_strava_data.csv')

cols_to_keep = [
  "id", "name", "start_date_local", "sport_type", "distance", "moving_time",
  "total_elevation_gain", "average_heartrate", "max_heartrate",
  "average_cadence", "average_speed", "max_speed",
  "kilojoules", "trainer", "manual"
]

df_clean = df[cols_to_keep]

### CONVERSION UNITES ###

# Distance : Mètres -> Kilomètres
df_clean['distance'] = df_clean['distance'] / 1000

# Temps : Secondes -> Heures (Format décimal pour l'analyse)
df_clean['moving_time'] = df_clean['moving_time'] / 3600

# Vitesse : Mètres/seconde -> Km/h (Lisible pour vélo/général)
df_clean['average_speed'] = df_clean['average_speed'] * 3.6
df_clean['max_speed'] = df_clean['max_speed'] * 3.6



### FEATURE ENGINEERING ###

## 1. RUNNING ##
is_run = df_clean['sport_type'] == 'Run'

#Pente moyenne
df_clean.loc[is_run, 'grade_pct'] = (df_clean['total_elevation_gain'] / (df_clean['distance'] * 1000)) * 100 

#Grade Adjusted Pace
df_clean.loc[is_run, 'gap_speed'] = df_clean['average_speed'] * (1 + (0.09 * df_clean['grade_pct']))

#Efficience 
df_clean.loc[is_run, 'hre_run'] = df_clean['gap_speed'] / df_clean['average_heartrate']

## 2. VELO ##
is_ride = df_clean['sport_type'] == 'Ride'

# VAM (Vitesse Ascensionnelle Moyenne) en m/h
df_clean.loc[is_ride, 'vam'] = df_clean['total_elevation_gain'] / (df_clean['moving_time'] * 60)


is_climbing = (df_clean['total_elevation_gain'] > 500) & is_ride

df_clean.loc[is_climbing, 'hre_ride'] = df_clean['average_speed'] / df_clean['average_heartrate']

df_clean.replace([np.inf, -np.inf], np.nan, inplace=True)

df_clean.to_csv('output/analytics_strava.csv', index=False)
print("Data Science terminée. Fichier enrichi généré.")
