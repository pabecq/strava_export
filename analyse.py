import pandas as pd
import numpy as np
from pathlib import Path

# --- CONFIGURATION & PHYSIOLOGY ---
# Update these values based on a recent field test or lab result.
PHYSIO = {
    'max_hr': 210,          # Real Max HR
    'rest_hr': 51,          # Real Resting HR
    'threshold_hr': 172,    # LTHR (Lactate Threshold HR)
    # Estimated TRIMP per hour for activities without Heart Rate data:
    'default_load_run': 60,     # ~Z2/Z3 Run
    'default_load_ride': 50,    # ~Z2 Ride
    'default_load_walk': 20,    # ~Z1 Walk
    'default_load_other': 45    # Gym/Swim etc
}

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / 'output/raw_strava_data.csv'
OUTPUT_FILE = BASE_DIR / 'output/analytics_strava.csv'

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"❌ Input file not found: {INPUT_FILE}")

print("🔄 Loading and Cleaning Data...")
df = pd.read_csv(INPUT_FILE)

# --- 1. CLEANING & NORMALIZATION ---

# Standardize Dates
df['start_date_local'] = pd.to_datetime(df['start_date_local'])
df = df.sort_values('start_date_local').reset_index(drop=True)

# Basic Time Components
df['date'] = df['start_date_local'].dt.normalize() # Remove time, keep date
df['year'] = df['start_date_local'].dt.year
df['month'] = df['start_date_local'].dt.month
df['week'] = df['start_date_local'].dt.isocalendar().week
df['day_of_year'] = df['start_date_local'].dt.dayofyear

# Unit Conversions
df['distance_km'] = df['distance'] / 1000
df['duration_h'] = df['moving_time'] / 3600
df['duration_min'] = df['moving_time'] / 60
df['speed_kmh'] = df['average_speed'] * 3.6

# Clean Artifacts
df = df[df['distance_km'] > 0.1].copy() # Remove GPS glitches
df.replace([np.inf, -np.inf], np.nan, inplace=True)

# Sport Classification
def classify_sport(t):
    if t in ['Run', 'TrailRun']: return 'Run'
    if t in ['Ride', 'GravelRide', 'VirtualRide', 'E-BikeRide']: return 'Ride'
    if t in ['Walk', 'Hike']: return 'Walk'
    if t in ['Swim']: return 'Swim'
    return 'Other'

df['sport_category'] = df['sport_type'].apply(classify_sport)

# --- 2. CALCULATE LOAD (TRIMP) ---

def calculate_trimp(row):
    """
    Calculates Banister's TRIMP.
    Equation: Duration(min) * HRR * 0.64 * e^(1.92 * HRR)
    """
    hr = row['average_heartrate']
    
    # 1. Reliable Data Case
    if pd.notna(hr) and hr > PHYSIO['rest_hr']:
        hr_reserve = (hr - PHYSIO['rest_hr']) / (PHYSIO['max_hr'] - PHYSIO['rest_hr'])
        trimp = row['duration_min'] * hr_reserve * 0.64 * np.exp(1.92 * hr_reserve)
        return trimp
    
    # 2. Missing Data Fallback (Physiologically Safer)
    sport = row['sport_category']
    if sport == 'Run': return row['duration_h'] * PHYSIO['default_load_run']
    if sport == 'Ride': return row['duration_h'] * PHYSIO['default_load_ride']
    if sport == 'Walk': return row['duration_h'] * PHYSIO['default_load_walk']
    return row['duration_h'] * PHYSIO['default_load_other']

df['trimp'] = df.apply(calculate_trimp, axis=1)

# --- 3. ADVANCED METRICS (CTL / ATL / TSB) ---
# This requires a continuous timeline. Fitness decays when you rest.
# We aggregate to daily totals first.

print("📉 Calculating Fitness (CTL) & Fatigue (ATL)...")

# Group by date to handle multiple workouts in one day
daily_load = df.groupby('date')['trimp'].sum().reset_index()

# Reindex to fill missing days with 0 Load
full_idx = pd.date_range(start=daily_load['date'].min(), end=daily_load['date'].max(), freq='D')
daily_stats = daily_load.set_index('date').reindex(full_idx, fill_value=0)

# Calculate Exponential Weighted Averages
# CTL (Fitness): 42-day time constant
daily_stats['ctl'] = daily_stats['trimp'].ewm(span=42, adjust=False).mean()

# ATL (Fatigue): 7-day time constant
daily_stats['atl'] = daily_stats['trimp'].ewm(span=7, adjust=False).mean()

# TSB (Form): Fitness - Fatigue
# Note: Usually TSB is calculated as Yesterday's CTL - Yesterday's ATL for "Today's Readiness".
# Here we calculate instantaneous balance.
daily_stats['tsb'] = daily_stats['ctl'] - daily_stats['atl']

# Merge metrics back to the main dataframe
# We map the daily stats to the activity based on the date
daily_stats = daily_stats.reset_index().rename(columns={'index': 'date'})
df = df.merge(daily_stats[['date', 'ctl', 'atl', 'tsb']], on='date', how='left')


# --- 4. EFFICIENCY METRICS (GAP & Decoupling) ---

# Grade Adjusted Pace (Simplified for Running)
# +1% grade ~ +4.5% energy cost (Minetti et al)
# Only apply to Runs with elevation
mask_run = df['sport_category'] == 'Run'
df['grade_pct'] = (df['total_elevation_gain'] / (df['distance'] + 1)) * 100 # Avoid div/0
df['gap_speed_kmh'] = df['speed_kmh']

# Apply GAP correction
df.loc[mask_run, 'gap_speed_kmh'] = df.loc[mask_run, 'speed_kmh'] + (df.loc[mask_run, 'grade_pct'] * 0.45)

# Efficiency Factor (EF) = Output / Input
# Valid only if HR exists
df['efficiency_factor'] = np.nan
mask_hr = df['average_heartrate'] > 0
df.loc[mask_hr, 'efficiency_factor'] = df.loc[mask_hr, 'gap_speed_kmh'] / df.loc[mask_hr, 'average_heartrate']


# --- 5. ZONES ---

def get_zone(hr):
    if pd.isna(hr) or hr == 0: return 'Unknown'
    # Simple 3-Zone Polarized Model
    z1_limit = 0.75 * PHYSIO['max_hr'] # Aerobic Threshold approx
    z2_limit = 0.88 * PHYSIO['max_hr'] # Anaerobic Threshold approx
    
    if hr < z1_limit: return 'Z1_Green'
    if hr < z2_limit: return 'Z2_Yellow'
    return 'Z3_Red'

df['intensity_zone'] = df['average_heartrate'].apply(get_zone)


# --- 6. CUMULATIVE STATS (By Year/Sport) ---
# Keeping your ghost runner logic, but ensuring it respects the sort order

df = df.sort_values('start_date_local')

for sport in ['Run', 'Ride']:
    col_name = f'cumul_dist_{sport.lower()}'
    df[col_name] = np.nan
    mask = df['sport_category'] == sport
    # Group by year, then cumsum distance
    df.loc[mask, col_name] = df[mask].groupby('year')['distance_km'].cumsum()

# Cumulative TRIMP (Global Load per year)
df['cumul_trimp'] = df.groupby('year')['trimp'].cumsum()


# --- EXPORT ---
# Filter columns to keep file size manageable
final_cols = [
    'id', 'name', 'start_date_local', 'date', 'year', 'day_of_year', 'week',
    'type', 'sport_category', 'distance_km', 'duration_h', 'total_elevation_gain',
    'average_heartrate', 'max_heartrate', 'trimp', 'ctl', 'atl', 'tsb',
    'speed_kmh', 'gap_speed_kmh', 'efficiency_factor', 'intensity_zone',
    'cumul_dist_run', 'cumul_dist_ride', 'cumul_trimp'
]

# Only keep columns that actually exist (in case of empty df)
cols_to_export = [c for c in final_cols if c in df.columns]

df[cols_to_export].to_csv(OUTPUT_FILE, index=False)
print(f"✅ Analysis Complete.")
print(f"📊 Latest Fitness (CTL): {df['ctl'].iloc[-1]:.1f}")
print(f"😴 Latest Fatigue (ATL): {df['atl'].iloc[-1]:.1f}")
print(f"⚖️  Form (TSB): {df['tsb'].iloc[-1]:.1f}")
print(f"💾 Saved to {OUTPUT_FILE}")