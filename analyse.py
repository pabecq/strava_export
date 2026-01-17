import pandas as pd
import numpy as np
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / 'output/raw_strava_data.csv'
OUTPUT_FILE = BASE_DIR / 'output/analytics_strava.csv'

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"❌ Input file not found: {INPUT_FILE}. Run fetch.py first.")

df = pd.read_csv(INPUT_FILE)

cols_to_keep = [
  "id", "name", "start_date_local", "sport_type", "distance", "moving_time",
  "total_elevation_gain", "average_heartrate", "max_heartrate",
  "average_cadence", "average_speed", "max_speed",
  "kilojoules", "trainer", "manual"
]

# Ensure we don't crash if columns are missing (common in empty exports)
existing_cols = [c for c in cols_to_keep if c in df.columns]
df_clean = df[existing_cols].copy()

### UNIT CONVERSION ###

# Distance: Meters -> km
df_clean['distance_km'] = df_clean['distance'] / 1000

# Time: Seconds -> Hours
df_clean['duration_h'] = df_clean['moving_time'] / 3600

# Speed: m/s -> km/h
df_clean['avg_speed_kmh'] = df_clean['average_speed'] * 3.6
df_clean['max_speed_kmh'] = df_clean['max_speed'] * 3.6

### FEATURE ENGINEERING ###

# Prevent division by zero
df_clean.replace([np.inf, -np.inf], np.nan, inplace=True)

## 1. RUNNING (Run + TrailRun) ##
# Strava differentiates Run and TrailRun. We want both.
is_run = df_clean['sport_type'].isin(['Run', 'TrailRun'])

# "Elevation Ratio" (Better name than grade_pct for summary data)
# This represents "How hilly was the route?" not "How steep was the hill?"
df_clean.loc[is_run, 'elevation_ratio_m_per_km'] = (
    df_clean['total_elevation_gain'] / df_clean['distance_km']
)

# Efficiency Proxy: Speed / HR 
# Only valid if HR data exists (> 0)
has_hr = df_clean['average_heartrate'] > 0
df_clean.loc[is_run & has_hr, 'aerobic_efficiency'] = (
    df_clean['avg_speed_kmh'] / df_clean['average_heartrate']
)

## 2. CYCLING ##
is_ride = df_clean['sport_type'].isin(['Ride', 'VirtualRide', 'GravelRide'])

# VAM (Global Approximation)
# Note: This is "Global VAM" (Total Elev / Total Time). 
# Real VAM requires segment data. This is useful only for comparison between rides.
df_clean.loc[is_ride, 'global_vam_m_h'] = (
    df_clean['total_elevation_gain'] / df_clean['duration_h']
)

# Climbing Classification
# A ride is "Climbing focused" if it has > 10m elevation gain per km
is_climbing_ride = (df_clean['total_elevation_gain'] / df_clean['distance_km']) > 10
df_clean.loc[is_ride, 'ride_category'] = np.where(is_climbing_ride, 'Hilly', 'Flat')

### CLEANUP & EXPORT ###

# Drop rows with 0 distance (manual entries or errors)
df_clean = df_clean[df_clean['distance'] > 0]

df_clean.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Analysis complete. Enriched data saved to {OUTPUT_FILE}")