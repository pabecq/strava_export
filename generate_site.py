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
OUTPUT_HTML = Path('/var/www/html/strava_dashboard.html') 
SYNC_ENDPOINT = "sync.php" 

# PALETTE
C_BG = "#0f172a"
C_CARD = "#1e293b"
C_TEXT = "#f8fafc"
C_CTL = "#3b82f6"
C_ATL = "#f43f5e"
C_TSB_POS = "#10b981"
C_TSB_NEG = "#f59e0b"
C_ACCENT = "#fc4c02"

# --- CHARGEMENT ---
if not DATA_FILE.exists():
    print("❌ Données introuvables.")
    exit()

df = pd.read_csv(DATA_FILE)
df['date'] = pd.to_datetime(df['date'])
df['start_date_local'] = pd.to_datetime(df['start_date_local'])
df_chart = df.sort_values('date').copy()

# --- MÉTRIQUES ---
if not df.empty:
    last_row = df_chart.iloc[-1]
    current_ctl = last_row.get('ctl', 0)
    current_atl = last_row.get('atl', 0)
    current_tsb = last_row.get('tsb', 0)
    
    date_7d_ago = last_row['date'] - datetime.timedelta(days=7)
    df_7d = df_chart[df_chart['date'] <= date_7d_ago]
    ramp_rate = current_ctl - df_7d.iloc[-1]['ctl'] if not df_7d.empty else 0
else:
    current_ctl = current_atl = current_tsb = ramp_rate = 0

# LOGIQUE HORS F-STRING POUR ÉVITER LE SYNTAX ERROR
status_text = "🚀 PRÊT À S'ÉCLATER" if current_tsb > -10 else "⚠️ ATTENTION SURCHAUFFE"
status_class = "text-success" if current_tsb > -10 else "text-warning"
last_sync_str = datetime.datetime.now().strftime('%d/%m à %H:%M')

# --- CHARTS ---
fig_pmc = make_subplots(specs=[[{"secondary_y": True}]])
fig_pmc.add_trace(go.Bar(
    x=df_chart['date'], y=df_chart['tsb'],
    name="Forme (TSB)",
    marker=dict(color=df_chart['tsb'].apply(lambda x: C_TSB_POS if x >= -10 else C_TSB_NEG)),
    opacity=0.4
), secondary_y=True)

fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['ctl'],
    name="Fitness (CTL)",
    mode='lines',
    line=dict(color=C_CTL, width=3),
    fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.1)'
), secondary_y=False)

fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['atl'],
    name="Fatigue (ATL)",
    mode='lines',
    line=dict(color=C_ATL, width=1.5, dash='dot')
), secondary_y=False)

fig_pmc.update_layout(
    template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=10, r=10, t=30, b=10), height=350,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified"
)
fig_pmc.update_yaxes(showgrid=False, secondary_y=True, range=[-60, 40])
fig_pmc.update_yaxes(showgrid=True, gridcolor='#334155', secondary_y=False)

df_run = df[df['sport_category'] == 'Run'].copy()
if not df_run.empty:
    fig_eff = px.scatter(df_run, x='start_date_local', y='efficiency_factor', 
                         color='average_heartrate', size='distance_km',
                         color_continuous_scale='Viridis', title="Efficience (Vitesse/FC)")
    fig_eff.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300)
else:
    fig_eff = go.Figure()

# --- TABLEAU ---
last_activities = df.sort_values('start_date_local', ascending=False).head(8)
table_html = ""
for _, row in last_activities.iterrows():
    icon = "🏃" if row['sport_category'] == 'Run' else "🚴" if row['sport_category'] == 'Ride' else "🏋️"
    dist = f"{row['distance_km']:.1f} km" if row['distance_km'] > 0 else "-"
    table_html += f"""
    <tr style="border-bottom: 1px solid #334155;">
        <td class="py-3">{icon} {row['start_date_local'].strftime('%d/%m')}</td>
        <td class="fw-bold">{str(row['name'])[:25]}</td>
        <td>{dist}</td>
        <td><span class="badge bg-secondary">{int(row['trimp'])} TRIMP</span></td>
    </tr>
    """

# --- HTML ---
html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>PIERRE-ANTOINE | LAB</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: {C_BG}; color: {C_TEXT}; font-family: 'Inter', sans-serif; }}
        .card {{ background-color: {C_CARD}; border: none; border-radius: 15px; }}
        .stat-value {{ font-size: 2.2rem; font-weight: 800; }}
        .stat-label {{ color: #94a3b8; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 1px; }}
        .btn-strava {{ background-color: {C_ACCENT}; color: white; border: none; font-weight: bold; border-radius: 30px; }}
    </style>
</head>
<body>
    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1 class="fw-black m-0">PERFORMANCE LAB</h1>
            <button id="syncBtn" class="btn btn-strava px-4" onclick="triggerSync()">🔄 SYNCHRONISER</button>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-md-3"><div class="card p-3"><div class="stat-label">Fitness</div><div class="stat-value text-info">{current_ctl:.1f}</div></div></div>
            <div class="col-md-3"><div class="card p-3"><div class="stat-label">Fatigue</div><div class="stat-value text-danger">{current_atl:.1f}</div></div></div>
            <div class="col-md-3"><div class="card p-3"><div class="stat-label">Forme</div><div class="stat-value">{current_tsb:.1f}</div></div></div>
            <div class="col-md-3"><div class="card p-3"><div class="stat-label">Ramp Rate</div><div class="stat-value">{ramp_rate:+.1f}</div></div></div>
        </div>

        <div class="row g-3">
            <div class="col-lg-8">
                <div class="card p-3 mb-3">{fig_pmc.to_html(full_html=False, include_plotlyjs='cdn')}</div>
                <div class="card p-3"><table class="table table-dark table-hover m-0">{table_html}</table></div>
            </div>
            <div class="col-lg-4">
                <div class="card p-3 mb-3">{fig_eff.to_html(full_html=False, include_plotlyjs=False)}</div>
                <div class="card p-4 text-center">
                    <p class="stat-label">Statut Actuel</p>
                    <h4 class="fw-bold {status_class}">{status_text}</h4>
                    <p class="small text-muted">Sync : {last_sync_str}</p>
                </div>
            </div>
        </div>
    </div>
    <script>
        function triggerSync() {{
            const btn = document.getElementById('syncBtn');
            btn.disabled = true;
            btn.innerText = "⏳ SYNCHRONISATION...";
            fetch('{SYNC_ENDPOINT}').then(() => {{ alert("Sync lancée !"); setTimeout(() => location.reload(), 5000); }});
        }}
    </script>
</body>
</html>
"""

with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f"✅ Dashboard généré : {OUTPUT_HTML}")