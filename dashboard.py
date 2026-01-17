import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# --- CONFIGURATION ---
st.set_page_config(page_title="Strava Performance Lab", page_icon="📈", layout="wide")
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / 'output/analytics_strava.csv'

# --- DATA LOADER ---
@st.cache_data
def load_data():
    if not DATA_FILE.exists():
        return None
    df = pd.read_csv(DATA_FILE)
    df['start_date_local'] = pd.to_datetime(df['start_date_local'])
    return df

df = load_data()

# --- HEADER ---
st.title("🏃‍♂️ Strava Performance Lab")
st.markdown("*> \"What gets measured gets managed. What gets ignored degrades.\"*")

if df is None:
    st.error("❌ No data found. Please run fetch.py first.")
    st.stop()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filters")
year_list = sorted(df['start_date_local'].dt.year.unique(), reverse=True)
selected_year = st.sidebar.selectbox("Select Year", year_list, index=0)

df_year = df[df['start_date_local'].dt.year == selected_year]

# --- KPI ROW ---
col1, col2, col3, col4 = st.columns(4)
total_dist = df_year['distance_km'].sum()
total_hours = df_year['duration_h'].sum()
total_elev = df_year['total_elevation_gain'].sum()
activity_count = len(df_year)

col1.metric("Total Distance", f"{total_dist:,.0f} km")
col2.metric("Total Time", f"{total_hours:,.0f} h")
col3.metric("Elevation Gain", f"{total_elev:,.0f} m")
col4.metric("Activities", activity_count)

st.divider()

# --- TABS ---
tab_run, tab_ride = st.tabs(["🏃 Running", "🚴 Cycling"])

# === RUNNING TAB ===
with tab_run:
    df_run = df_year[df_year['sport_type'].isin(['Run', 'TrailRun'])].copy()
    
    if not df_run.empty:
        # 1. VOLUME TREND (Weekly)
        st.subheader("Weekly Volume Consistency")
        df_run['week'] = df_run['start_date_local'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_vol = df_run.groupby('week')['distance_km'].sum().reset_index()
        
        fig_vol = px.bar(weekly_vol, x='week', y='distance_km', title="Weekly Running Distance (km)")
        # Add a moving average line to show consistency
        fig_vol.add_trace(go.Scatter(x=weekly_vol['week'], y=weekly_vol['distance_km'].rolling(4).mean(), mode='lines', name='4-Week Avg', line=dict(color='red')))
        st.plotly_chart(fig_vol, use_container_width=True)

        # 2. EFFICIENCY SCATTER (The "Am I getting fitter?" Chart)
        st.subheader("Aerobic Efficiency (Speed vs HR)")
        # Filter out junk data (HR < 100 or super short runs)
        valid_runs = df_run[(df_run['average_heartrate'] > 100) & (df_run['distance_km'] > 3)]
        
        if not valid_runs.empty:
            fig_eff = px.scatter(
                valid_runs, 
                x='average_heartrate', 
                y='avg_speed_kmh', 
                color='start_date_local',
                size='distance_km',
                title="Efficiency: Are you faster at the same HR? (Darker = Newer)",
                trendline="ols" # Requires statsmodels
            )
            st.plotly_chart(fig_eff, use_container_width=True)
        else:
            st.warning("Not enough heart rate data for efficiency analysis.")
    else:
        st.info("No running data for this year.")

# === CYCLING TAB ===
with tab_ride:
    df_ride = df_year[df_year['sport_type'].isin(['Ride', 'VirtualRide', 'GravelRide'])].copy()
    
    if not df_ride.empty:
        col_c1, col_c2 = st.columns(2)
        
        # 1. ELEVATION PROFILE
        with col_c1:
            st.subheader("Ride Profile Distribution")
            fig_pie = px.pie(df_ride, names='ride_category', title="Hilly vs Flat Rides")
            st.plotly_chart(fig_pie, use_container_width=True)
            
        # 2. VAM DISTRIBUTION
        with col_c2:
            st.subheader("Global VAM (Ascension Speed)")
            fig_hist = px.histogram(df_ride, x='global_vam_m_h', nbins=20, title="VAM Distribution (m/h)")
            st.plotly_chart(fig_hist, use_container_width=True)
            
        # 3. SCATTER PLOT
        st.subheader("Ride Duration vs Intensity (HR)")
        fig_ride_scatter = px.scatter(df_ride, x='duration_h', y='average_heartrate', size='total_elevation_gain', color='sport_type')
        st.plotly_chart(fig_ride_scatter, use_container_width=True)
        
    else:
        st.info("No cycling data for this year.")