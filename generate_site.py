import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import datetime
import numpy as np

# --- CONFIG ---
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / 'output/analytics_strava.csv'
OUTPUT_HTML = Path('/var/www/html/strava_dashboard.html') # Adjust this path for your server

# Colors (Dark Mode Palette)
C_BG = "#121212"
C_CARD = "#1e1e1e"
C_TEXT = "#e0e0e0"
C_ACCENT = "#fc4c02" # Strava Orange
C_MUTED = "#636e72"

# --- LOAD DATA ---
if not DATA_FILE.exists():
    print("❌ No data found. Run fetch.py and analyse.py first.")
    exit()

df = pd.read_csv(DATA_FILE)

# Date Prep
df['start_date_local'] = pd.to_datetime(df['start_date_local'])
df['year'] = df['start_date_local'].dt.year
df['day_of_year'] = df['start_date_local'].dt.dayofyear
df['week'] = df['start_date_local'].dt.isocalendar().week

# Current Context
today = datetime.datetime.now()
current_year = today.year
previous_year = current_year - 1

df_curr = df[df['year'] == current_year].copy()
df_prev = df[df['year'] == previous_year].copy()

# --- KPI CALCULATIONS ---
total_trimp = df_curr['trimp'].sum()
total_hours = df_curr['duration_h'].sum()
run_km = df_curr[df_curr['sport_category'] == 'Run']['distance_km'].sum()
ride_km = df_curr[df_curr['sport_category'] == 'Ride']['distance_km'].sum()

# Prediction (Linear projection based on day of year)
days_elapsed = today.timetuple().tm_yday
if days_elapsed > 10:
    proj_trimp = (total_trimp / days_elapsed) * 365
else:
    proj_trimp = 0

# --- CHART 1: THE GHOST ATHLETE (Cumulative Load) ---
# We compare Cumulative TRIMP, not KM. This normalizes Run vs Bike.
def get_cumul_trimp(d):
    if d.empty: return pd.DataFrame()
    # Sort and Cumsum
    d = d.sort_values('day_of_year')
    d['cumul_load'] = d['trimp'].cumsum()
    return d[['day_of_year', 'cumul_load']]

c_curr = get_cumul_trimp(df_curr)
c_prev = get_cumul_trimp(df_prev)

fig_ghost = go.Figure()

# Previous Year (Ghost)
if not c_prev.empty:
    fig_ghost.add_trace(go.Scatter(
        x=c_prev['day_of_year'], y=c_prev['cumul_load'],
        mode='lines', name=f'{previous_year} (Ghost)',
        line=dict(color=C_MUTED, width=2, dash='dot')
    ))

# Current Year
if not c_curr.empty:
    fig_ghost.add_trace(go.Scatter(
        x=c_curr['day_of_year'], y=c_curr['cumul_load'],
        mode='lines', name=f'{current_year}',
        line=dict(color=C_ACCENT, width=4)
    ))
    # Marker for today
    last = c_curr.iloc[-1]
    fig_ghost.add_trace(go.Scatter(
        x=[last['day_of_year']], y=[last['cumul_load']],
        mode='markers', marker=dict(color='white', size=8), showlegend=False
    ))

fig_ghost.update_layout(
    title="📈 Year vs Year (Training Load)",
    paper_bgcolor=C_CARD, plot_bgcolor=C_CARD,
    font=dict(color=C_TEXT),
    xaxis=dict(showgrid=False, title="Day of Year"),
    yaxis=dict(gridcolor='#333', title="Cumulative TRIMP"),
    margin=dict(l=40, r=20, t=40, b=40),
    height=350,
    hovermode="x unified"
)

# --- CHART 2: WEEKLY CONSISTENCY (Bar) ---
# Sum TRIMP per week
weekly_load = df_curr.groupby('week')['trimp'].sum().reset_index()

fig_consist = go.Figure(go.Bar(
    x=weekly_load['week'], y=weekly_load['trimp'],
    marker_color=C_ACCENT, opacity=0.8
))
fig_consist.add_hline(y=weekly_load['trimp'].mean(), line_dash="dot", line_color="white", annotation_text="Avg")

fig_consist.update_layout(
    title="📅 Weekly Load Consistency",
    paper_bgcolor=C_CARD, plot_bgcolor=C_CARD,
    font=dict(color=C_TEXT),
    xaxis=dict(showgrid=False, title="Week #"),
    yaxis=dict(showgrid=False, title="TRIMP"),
    height=250, margin=dict(l=20, r=20, t=40, b=20)
)

# --- CHART 3: INTENSITY DISTRIBUTION (Donut) ---
# Are you training polarized?
zone_counts = df_curr['intensity_zone'].value_counts()
colors_zones = {'Z1_Recovery': '#00b894', 'Z2_Aerobic': '#fdcb6e', 'Z3_High': '#d63031', 'Unknown': '#636e72'}
pie_colors = [colors_zones.get(x, '#636e72') for x in zone_counts.index]

fig_zones = go.Figure(data=[go.Pie(
    labels=zone_counts.index, values=zone_counts.values, hole=.6,
    marker=dict(colors=pie_colors), textinfo='label+percent'
)])
fig_zones.update_layout(
    title="⚡ Intensity Distribution",
    paper_bgcolor=C_CARD, plot_bgcolor=C_CARD,
    font=dict(color=C_TEXT),
    height=250, margin=dict(l=20, r=20, t=40, b=20),
    showlegend=False
)

# --- CHART 4: RUNNING EFFICIENCY TREND ---
# Efficiency Factor = GAP Speed / HR. (Rising = Good)
df_eff = df_curr[
    (df_curr['sport_category'] == 'Run') & 
    (df_curr['distance_km'] > 5) & 
    (df_curr['average_heartrate'] > 120)
].copy()

if not df_eff.empty:
    fig_eff = px.scatter(
        df_eff, x='start_date_local', y='efficiency_factor',
        color='average_heartrate', size='distance_km',
        color_continuous_scale='RdYlGn_r', # Red=HighHR, Green=LowHR
        title="🏃 Running Efficiency Trend (Rising = Fitter)"
    )
    fig_eff.update_layout(
        paper_bgcolor=C_CARD, plot_bgcolor=C_CARD,
        font=dict(color=C_TEXT),
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(gridcolor='#333', title="Eff. Factor"),
        height=300, margin=dict(l=20, r=20, t=40, b=20)
    )
    # Add Trendline
    z = np.polyfit(range(len(df_eff)), df_eff['efficiency_factor'], 1)
    p = np.poly1d(z)
    fig_eff.add_trace(go.Scatter(
        x=df_eff['start_date_local'], y=p(range(len(df_eff))),
        mode='lines', name='Trend', line=dict(color='white', width=1, dash='dot')
    ))
else:
    fig_eff = go.Figure()
    fig_eff.update_layout(title="Not enough Running Data", paper_bgcolor=C_CARD, font=dict(color=C_TEXT))

# --- LAST ACTIVITIES TABLE ---
last_5 = df.sort_values('start_date_local', ascending=False).head(5)
table_rows = ""
for _, row in last_5.iterrows():
    date_str = row['start_date_local'].strftime("%d %b")
    icon = "🏃" if row['sport_category'] == 'Run' else "🚴" if row['sport_category'] == 'Ride' else "🏋️"
    trimp_val = int(row['trimp'])
    
    # Color code TRIMP
    trimp_color = "#00b894" if trimp_val < 50 else "#fdcb6e" if trimp_val < 150 else "#d63031"
    
    table_rows += f"""
    <tr style="border-bottom: 1px solid #333;">
        <td style="padding:12px;">{icon} <span style="color:#aaa">{date_str}</span></td>
        <td style="padding:12px;"><b>{str(row['name'])[:25]}</b></td>
        <td style="padding:12px;">{row['distance_km']:.1f} km</td>
        <td style="padding:12px;"><span style="color:{trimp_color}; font-weight:bold;">{trimp_val}</span> <small>Load</small></td>
    </tr>
    """

# --- HTML GENERATION ---
html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Pro Analytics</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: {C_BG}; color: {C_TEXT}; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        .card {{ background-color: {C_CARD}; border: 1px solid #333; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 20px; }}
        .metric-val {{ font-size: 2.2rem; font-weight: 800; color: white; margin-bottom: 0; line-height: 1.1; }}
        .metric-label {{ font-size: 0.85rem; text-transform: uppercase; color: #888; letter-spacing: 1px; font-weight: 600; }}
        .metric-sub {{ font-size: 0.8rem; color: {C_ACCENT}; }}
        h4 {{ font-weight: 700; letter-spacing: -0.5px; color: white; }}
        .table {{ color: #ccc; }}
    </style>
</head>
<body>
    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h2 class="mb-0">🔥 Performance Lab</h2>
                <small class="text-muted">Last sync: {datetime.datetime.now().strftime("%d/%m %H:%M")}</small>
            </div>
            <span class="badge bg-warning text-dark">Beta v2.0</span>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-6 col-md-3">
                <div class="card p-3">
                    <div class="metric-val">{total_trimp:,.0f}</div>
                    <div class="metric-label">Total Load (TRIMP)</div>
                    <div class="metric-sub">Proj: {proj_trimp:,.0f}</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card p-3">
                    <div class="metric-val">{total_hours:,.0f}h</div>
                    <div class="metric-label">Moving Time</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card p-3">
                    <div class="metric-val">{run_km:,.0f} <small style="font-size:1rem">km</small></div>
                    <div class="metric-label">Running</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card p-3">
                    <div class="metric-val">{ride_km:,.0f} <small style="font-size:1rem">km</small></div>
                    <div class="metric-label">Cycling</div>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-lg-8">
                <div class="card p-1">
                    {fig_ghost.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
            </div>
            <div class="col-lg-4">
                <div class="card p-1">
                    {fig_consist.to_html(full_html=False, include_plotlyjs=False)}
                </div>
                <div class="card p-1 mb-0">
                    {fig_zones.to_html(full_html=False, include_plotlyjs=False)}
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-6">
                <div class="card h-100">
                    <div class="card-header bg-transparent border-bottom border-secondary text-white fw-bold">
                        📊 Recent Activities
                    </div>
                    <div class="card-body p-0">
                        <table class="table table-borderless m-0">
                            {table_rows}
                        </table>
                    </div>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="card h-100 p-1">
                    {fig_eff.to_html(full_html=False, include_plotlyjs=False)}
                </div>
            </div>
        </div>
        
        <div class="text-center mt-5 text-muted small">
            Generated automatically by Python on Tinkerboard.
        </div>
    </div>
</body>
</html>
"""

# --- SAVE ---
try:
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Dashboard successfully generated at: {OUTPUT_HTML}")
except Exception as e:
    print(f"❌ Error writing HTML file: {e}")
    # Fallback to local dir for testing
    local_path = BASE_DIR / "strava_dashboard.html"
    with open(local_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"⚠️ Saved to local directory instead: {local_path}")