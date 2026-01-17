import pandas as pd
import numpy as np
from pathlib import Path

# --- CONFIGURATION ---
# ⚠️ ADJUST THESE TO YOUR PHYSIOLOGY FOR ACCURACY ⚠️
MAX_HR = 210      # Your estimated Max Heart Rate
REST_HR = 50      # Your Resting Heart Rate
THRESHOLD_HR = 172 # Your Anaerobic Threshold (approx)

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / 'output/raw_strava_data.csv'
OUTPUT_FILE = BASE_DIR / 'output/analytics_strava.csv'

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"❌ Input file not found: {INPUT_FILE}. Run fetch.py first.")

print("🔄 Loading data...")
df = pd.read_csv(INPUT_FILE)

# --- 1. BASIC CLEANING ---

# Keep relevant columns only (handling missing ones safely)
cols_wanted = [
    "id", "name", "start_date", "start_date_local", "type", "sport_type", 
    "distance", "moving_time", "elapsed_time", "total_elevation_gain", 
    "average_heartrate", "max_heartrate", "average_cadence", 
    "average_speed", "max_speed", "suffer_score"
]
existing_cols = [c for c in cols_wanted if c in df.columns]
df = df[existing_cols].copy()

# Date conversions
df['start_date_local'] = pd.to_datetime(df['start_date_local'])
df['year'] = df['start_date_local'].dt.year
df['month'] = df['start_date_local'].dt.month
df['week'] = df['start_date_local'].dt.isocalendar().week
df['day_of_year'] = df['start_date_local'].dt.dayofyear

# Unit Conversions
df['distance_km'] = df['distance'] / 1000
df['duration_h'] = df['moving_time'] / 3600
df['duration_min'] = df['moving_time'] / 60
df['speed_kmh'] = df['average_speed'] * 3.6
df['pace_min_km'] = 60 / df['speed_kmh'] # Only useful for display

# Fix Infinite/NaN values
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df = df.dropna(subset=['distance_km', 'moving_time']) # Drop empty activities
df = df[df['distance_km'] > 0.1] # Drop artifacts

# --- 2. ADVANCED METRICS ---

# A. Banister TRIMP (Training Impulse)
# The Gold Standard for measuring "Load" across different sports
# Formula: Duration_min * HR_Reserve_Ratio * 0.64 * exp(1.92 * HR_Reserve_Ratio)
# If HR is missing, we estimate Load based on Moving Time * Moderate Intensity factor
def calculate_trimp(row):
    if pd.isna(row['average_heartrate']) or row['average_heartrate'] == 0:
        # Fallback: Estimate 40 TRIMP per hour (Moderate effort)
        return row['duration_h'] * 40
    
    hr_res = (row['average_heartrate'] - REST_HR) / (MAX_HR - REST_HR)
    trimp = row['duration_min'] * hr_res * 0.64 * np.exp(1.92 * hr_res)
    return trimp

df['trimp'] = df.apply(calculate_trimp, axis=1)

# B. Grade Adjusted Speed (GAP) Approximation
# Very rough estimation: +1% grade ≈ +3% energy cost (Minetti et al. simplified)
# We only calculate this for Runs
df['grade_pct'] = (df['total_elevation_gain'] / df['distance']) * 100
df['gap_speed_kmh'] = df['speed_kmh']
mask_run = df['sport_type'].isin(['Run', 'TrailRun'])

# If running uphill, increase speed to represent flat equivalent
# (Simplified: add 0.3 km/h for every 1% gradient)
df.loc[mask_run, 'gap_speed_kmh'] = df.loc[mask_run, 'speed_kmh'] + (df.loc[mask_run, 'grade_pct'] * 0.3)

# C. Efficiency Factor (EF)
# Output (Speed/Power) divided by Input (Heart Rate)
# Using GAP speed makes this metric comparable between Hilly and Flat runs.
df['efficiency_factor'] = df['gap_speed_kmh'] / df['average_heartrate']
df.loc[df['average_heartrate'] == 0, 'efficiency_factor'] = np.nan

# --- 3. CLASSIFICATION ---

# Normalize Sport Types
def classify_sport(t):
    if t in ['Run', 'TrailRun']: return 'Run'
    if t in ['Ride', 'GravelRide', 'VirtualRide', 'E-BikeRide']: return 'Ride'
    if t in ['Swim']: return 'Swim'
    if t in ['WeightTraining', 'Workout', 'Crossfit']: return 'Strength'
    return 'Other'

df['sport_category'] = df['sport_type'].apply(classify_sport)

# Intensity Zones (Polarized Training Check)
# Z1: Recovery (<70%), Z2: Aerobic (<80%), Z3: Tempo/Threshold+ (>80%)
def get_zone(hr):
    if pd.isna(hr) or hr == 0: return 'Unknown'
    pct = hr / MAX_HR
    if pct < 0.70: return 'Z1_Recovery'
    if pct < 0.82: return 'Z2_Aerobic'
    return 'Z3_High'

df['intensity_zone'] = df['average_heartrate'].apply(get_zone)

# --- 4. CUMULATIVE STATS (The "Ghost Runner" Fix) ---
# We calculate cumulative sums per year AND per sport so we don't mix them up.

df = df.sort_values('start_date_local')

# Helper for cumulative sum by year/sport
def calculate_cumulative(df, metric, sport):
    col_name = f'cumul_{metric}_{sport.lower()}'
    # Filter for sport
    mask = df['sport_category'] == sport
    # Group by year and cumsum
    df.loc[mask, col_name] = df[mask].groupby('year')[metric].cumsum()
    # Fill NaN (days where you didn't do this sport) with ffill later or 0? 
    # Better to leave NaN for plotting points, but for "totals" we need care.
    return df

df['cumul_dist_run'] = np.nan
df['cumul_dist_ride'] = np.nan
df['cumul_trimp'] = np.nan

df = calculate_cumulative(df, 'distance_km', 'Run')
df = calculate_cumulative(df, 'distance_km', 'Ride')
# TRIMP is global (all sports combined)
df['cumul_trimp'] = df.groupby('year')['trimp'].cumsum()


# --- 5. EXPORT ---
df.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Analysis complete. {len(df)} activities processed.")
print(f"📊 Global TRIMP calculated. Data saved to {OUTPUT_FILE}")