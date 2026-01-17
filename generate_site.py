import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
import datetime
import numpy as np

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / 'output/analytics_strava.csv'
# ⚠️ Update this path to where your web server hosts the file
OUTPUT_HTML = Path('/var/www/html/strava_dashboard.html') 
SYNC_ENDPOINT = "sync.php" # The file the button will trigger

# PALETTE (Dark Mode Professional)
C_BG = "#0f1014"      # Deep background
C_CARD = "#1b1e23"    # Card background
C_TEXT = "#e2e8f0"
C_CTL = "#3b82f6"     # Blue (Fitness)
C_ATL = "#ec4899"     # Pink (Fatigue)
C_TSB_POS = "#22c55e" # Green (Fresh)
C_TSB_NEG = "#ef4444" # Red (Tired)
C_ACCENT = "#f97316"  # Strava Orange

# --- LOAD DATA ---
if not DATA_FILE.exists():
    print("❌ No data found. Run fetch.py and analyse.py first.")
    exit()

df = pd.read_csv(DATA_FILE)
df['date'] = pd.to_datetime(df['date'])
df['start_date_local'] = pd.to_datetime(df['start_date_local'])

# Sort chronologically for charting
df_chart = df.sort_values('date').copy()

# Latest Metrics (Snapshot)
if not df.empty:
    last_row = df_chart.iloc[-1]
    current_ctl = last_row.get('ctl', 0)
    current_atl = last_row.get('atl', 0)
    current_tsb = last_row.get('tsb', 0)
    
    # Calculate Ramp Rate (Change in CTL over last 7 days)
    # Filter to 7 days ago
    date_7d_ago = last_row['date'] - datetime.timedelta(days=7)
    row_7d = df_chart[df_chart['date'] <= date_7d_ago].iloc[-1] if not df_chart[df_chart['date'] <= date_7d_ago].empty else None
    
    if row_7d is not None:
        ramp_rate = current_ctl - row_7d['ctl']
    else:
        ramp_rate = 0
else:
    current_ctl = current_atl = current_tsb = ramp_rate = 0

# --- CHART 1: THE PMC (Performance Management Chart) ---
# Left Axis: CTL & ATL. Right Axis: TSB (Bar/Area)

fig_pmc = make_subplots(specs=[[{"secondary_y": True}]])

# 1. TSB (Form) - Area/Bar behind
# We split into positive and negative for coloring
fig_pmc.add_trace(go.Bar(
    x=df_chart['date'], y=df_chart['tsb'],
    name="Form (TSB)",
    marker=dict(color=df_chart['tsb'].apply(lambda x: C_TSB_POS if x >= 0 else C_TSB_NEG)),
    opacity=0.3
), secondary_y=True)

# 2. CTL (Fitness) - Solid Line
fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['ctl'],
    name="Fitness (CTL)",
    mode='lines',
    line=dict(color=C_CTL, width=3),
    fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.1)'
), secondary_y=False)

# 3. ATL (Fatigue) - Dotted Line
fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['atl'],
    name="Fatigue (ATL)",
    mode='lines',
    line=dict(color=C_ATL, width=1, dash='dot')
), secondary_y=False)

fig_pmc.update_layout(
    title="⚡ Performance Management Chart (PMC)",
    template="plotly_dark",
    paper_bgcolor=C_CARD, plot_bgcolor=C_CARD,
    font=dict(color=C_TEXT),
    margin=dict(l=20, r=20, t=40, b=20),
    height=400,
    legend=dict(orientation="h", y=1.1),
    hovermode="x unified"
)
fig_pmc.update_yaxes(title_text="Load (CTL/ATL)", secondary_y=False, showgrid=True, gridcolor='#333')
fig_pmc.update_yaxes(title_text="Form (TSB)", secondary_y=True, showgrid=False, range=[-50, 50])


# --- CHART 2: WEEKLY VOLUME & INTENSITY ---
weekly = df.groupby(['year', 'week']).agg({
    'trimp': 'sum', 
    'distance_km': 'sum', 
    'start_date_local': 'min'
}).reset_index()
# Filter last 52 weeks
weekly = weekly.sort_values('start_date_local').tail(52)

fig_vol = go.Figure()
fig_vol.add_trace(go.Bar(
    x=weekly['start_date_local'], y=weekly['trimp'],
    marker_color=C_ACCENT, name="Weekly Load"
))
# Add moving average
fig_vol.add_trace(go.Scatter(
    x=weekly['start_date_local'], y=weekly['trimp'].rolling(4).mean(),
    mode='lines', line=dict(color='white', width=2, dash='solid'), name="4w Avg"
))

fig_vol.update_layout(
    title="📅 Weekly Load Consistency (Last 52w)",
    template="plotly_dark",
    paper_bgcolor=C_CARD, plot_bgcolor=C_CARD,
    font=dict(color=C_TEXT),
    margin=dict(l=20, r=20, t=40, b=20),
    height=250,
    showlegend=False
)

# --- CHART 3: EFFICIENCY FACTOR (Scatter) ---
# Running Efficiency only
df_eff = df[
    (df['sport_category'] == 'Run') & 
    (df['efficiency_factor'] > 0) & 
    (df['distance_km'] > 4)
].copy()

if not df_eff.empty:
    fig_eff = px.scatter(
        df_eff, x='date', y='efficiency_factor',
        color='average_heartrate', size='distance_km',
        color_continuous_scale='RdYlGn_r',
        title="🏃 Efficiency Factor Trend"
    )
    # Trendline
    z = np.polyfit(range(len(df_eff)), df_eff['efficiency_factor'], 1)
    p = np.poly1d(z)
    fig_eff.add_trace(go.Scatter(
        x=df_eff['date'], y=p(range(len(df_eff))),
        mode='lines', name='Trend', line=dict(color='white', width=2)
    ))
else:
    fig_eff = go.Figure()

fig_eff.update_layout(
    template="plotly_dark", paper_bgcolor=C_CARD, plot_bgcolor=C_CARD,
    font=dict(color=C_TEXT), height=300, margin=dict(l=20, r=20, t=40, b=20)
)

# --- TABLE GENERATION ---
last_5 = df.sort_values('start_date_local', ascending=False).head(5)
table_rows = ""
for _, row in last_5.iterrows():
    s_cat = row['sport_category']
    icon = "🏃" if s_cat == 'Run' else "🚴" if s_cat == 'Ride' else "🏊" if s_cat == 'Swim' else "🏋️"
    
    # Format Efficiency
    eff_display = f"{row['efficiency_factor']:.2f}" if pd.notna(row.get('efficiency_factor')) else "-"
    
    # Format Zone
    zone_color = "#ef4444" if "Z3" in str(row['intensity_zone']) else "#eab308" if "Z2" in str(row['intensity_zone']) else "#22c55e"
    
    table_rows += f"""
    <tr style="border-bottom: 1px solid #333; vertical-align: middle;">
        <td class="py-3 ps-3">{icon} <span class="text-secondary small">{row['start_date_local'].strftime('%d %b')}</span></td>
        <td class="fw-bold">{str(row['name'])[:30]}</td>
        <td>{row['distance_km']:.1f} <small class="text-muted">km</small></td>
        <td><span class="badge" style="background-color: #333; border: 1px solid {zone_color}">{int(row['trimp'])} TSS</span></td>
        <td class="text-end pe-3"><small class="text-muted">EF:</small> {eff_display}</td>
    </tr>
    """

# --- HTML TEMPLATE ---
html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Athlete Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {{ --bg-color: {C_BG}; --card-color: {C_CARD}; --accent: {C_ACCENT}; }}
        body {{ background-color: var(--bg-color); color: {C_TEXT}; font-family: 'Inter', system-ui, sans-serif; }}
        .card {{ background-color: var(--card-color); border: 1px solid #333; border-radius: 16px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5); }}
        .metric-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; font-weight: 600; }}
        .metric-value {{ font-size: 2.5rem; font-weight: 800; line-height: 1; margin: 10px 0; }}
        .metric-sub {{ font-size: 0.85rem; }}
        .btn-sync {{ background-color: var(--accent); border: none; font-weight: 700; color: white; transition: all 0.2s; }}
        .btn-sync:hover {{ background-color: #ea580c; transform: translateY(-1px); }}
        .btn-sync:disabled {{ background-color: #555; cursor: not-allowed; }}
        
        /* Utility Colors */
        .text-fitness {{ color: {C_CTL}; }}
        .text-fatigue {{ color: {C_ATL}; }}
        .text-fresh {{ color: {C_TSB_POS}; }}
        .text-tired {{ color: {C_TSB_NEG}; }}
    </style>
</head>
<body>
    <div class="container-fluid px-4 py-4" style="max-width: 1400px;">
        <div class="d-flex justify-content-between align-items-center mb-5">
            <div>
                <h2 class="fw-bold mb-0">PERFORMANCE LAB</h2>
                <small class="text-muted">Last Data: {datetime.datetime.now().strftime("%d %b %H:%M")}</small>
            </div>
            <button id="syncBtn" class="btn btn-sync px-4 py-2 rounded-pill" onclick="triggerSync()">
                🔄 Sync Strava
            </button>
        </div>

        <div class="row g-4 mb-4">
            <div class="col-md-3">
                <div class="card p-4 h-100 position-relative overflow-hidden">
                    <div class="metric-title">Fitness (CTL)</div>
                    <div class="metric-value text-fitness">{current_ctl:.0f}</div>
                    <div class="metric-sub text-muted">42-day Avg Load</div>
                    <div style="position:absolute; right: -10px; top: -10px; opacity: 0.1;">
                        <span style="font-size: 8rem;">📈</span>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card p-4 h-100">
                    <div class="metric-title">Fatigue (ATL)</div>
                    <div class="metric-value text-fatigue">{current_atl:.0f}</div>
                    <div class="metric-sub text-muted">7-day Avg Load</div>
                </div>
            </div>

            <div class="col-md-3">
                <div class="card p-4 h-100">
                    <div class="metric-title">Form (TSB)</div>
                    <div class="metric-value {'text-fresh' if current_tsb >= -10 else 'text-tired'}">
                        {current_tsb:+.0f}
                    </div>
                    <div class="metric-sub text-muted">Readiness to Perform</div>
                </div>
            </div>

             <div class="col-md-3">
                <div class="card p-4 h-100">
                    <div class="metric-title">Ramp Rate</div>
                    <div class="metric-value {'text-fresh' if ramp_rate < 6 else 'text-tired'}">
                        {ramp_rate:+.1f}
                    </div>
                    <div class="metric-sub text-muted">Weekly CTL Change (Target < 5)</div>
                </div>
            </div>
        </div>

        <div class="row g-4 mb-4">
            <div class="col-lg-8">
                <div class="card p-1">
                    {fig_pmc.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
            </div>
            <div class="col-lg-4">
                <div class="card p-1 h-100">
                    {fig_vol.to_html(full_html=False, include_plotlyjs=False)}
                </div>
            </div>
        </div>

        <div class="row g-4">
            <div class="col-lg-6">
                <div class="card h-100">
                    <div class="card-header bg-transparent border-bottom border-secondary text-white fw-bold py-3">
                        📋 Recent Training
                    </div>
                    <div class="table-responsive">
                        <table class="table table-dark table-borderless table-hover m-0">
                            {table_rows}
                        </table>
                    </div>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="card p-1 h-100">
                     {fig_eff.to_html(full_html=False, include_plotlyjs=False)}
                </div>
            </div>
        </div>
        
        <div class="mt-5 text-center text-muted small">
            Generated by Performance Lab v2.0
        </div>
    </div>

    <script>
        function triggerSync() {{
            const btn = document.getElementById('syncBtn');
            const originalText = btn.innerText;
            
            if(!confirm("Launch sync process? This may take a minute.")) return;

            btn.disabled = true;
            btn.innerText = "⏳ Running...";

            fetch('{SYNC_ENDPOINT}')
            .then(response => response.text())
            .then(data => {{
                console.log(data);
                alert("✅ Sync command sent! Reload the page in a few seconds.");
                btn.innerText = "✅ Done";
                setTimeout(() => {{ window.location.reload(); }}, 2000);
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert("❌ Sync failed. Check console.");
                btn.disabled = false;
                btn.innerText = originalText;
            }});
        }}
    </script>
</body>
</html>
"""

# --- SAVE ---
try:
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Dashboard generated: {OUTPUT_HTML}")
except Exception as e:
    # Fallback
    local = BASE_DIR / 'strava_dashboard.html'
    with open(local, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"⚠️ Permission Error. Saved locally: {local}")