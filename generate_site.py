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
SYNC_ENDPOINT = Path("/var/www/html/refresh.php")

# PALETTE PROFESSIONNELLE (Light Mode)
C_BG = "#f1f5f9"
C_CARD = "#ffffff"
C_TEXT = "#0f172a"
C_SUBTEXT = "#64748b"
C_CTL = "#2563eb"      # Fitness
C_ATL = "#e11d48"      # Fatigue
C_TSB_POS = "#10b981"  # Forme +
C_TSB_NEG = "#f59e0b"  # Forme -
C_ACCENT = "#fc4c02"

# --- CHARGEMENT & NORMALISATION ---
if not DATA_FILE.exists():
    print("❌ Données introuvables. Lancez d'abord analyse.py")
    exit()

df = pd.read_csv(DATA_FILE)

# Correction du bug de Timezone
df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
df['start_date_local'] = pd.to_datetime(df['start_date_local']).dt.tz_localize(None)

# --- FILTRAGE (90 JOURS) ---
now = datetime.datetime.now()
cutoff_date = now - datetime.timedelta(days=90)
df_chart = df[df['date'] >= cutoff_date].sort_values('date').copy()

# --- MÉTRIQUES DE PERFORMANCE GLOBALES ---
if not df.empty:
    last_row = df.sort_values('date').iloc[-1]
    current_ctl = last_row.get('ctl', 0)
    current_atl = last_row.get('atl', 0)
    current_tsb = last_row.get('tsb', 0)
    
    date_7d_ago = last_row['date'] - datetime.timedelta(days=7)
    df_prev = df[df['date'] <= date_7d_ago]
    ramp_rate = current_ctl - df_prev.iloc[-1]['ctl'] if not df_prev.empty else 0
else:
    current_ctl = current_atl = current_tsb = ramp_rate = 0

# LOGIQUE DE STATUT
if current_tsb < -30:
    status_text, status_class = "SURCHARGE (Risque)", "text-danger"
elif -30 <= current_tsb < -10:
    status_text, status_class = "OPTIMAL (Progression)", "text-success"
elif -10 <= current_tsb < 5:
    status_text, status_class = "MAINTIEN (Neutre)", "text-primary"
else:
    status_text, status_class = "TRANSITION (Récup)", "text-warning"

last_sync_str = now.strftime('%d/%m à %H:%M')

# --- GRAPHIQUE PRINCIPAL (PMC) ---
fig_pmc = make_subplots(specs=[[{"secondary_y": True}]])
fig_pmc.add_trace(go.Bar(
    x=df_chart['date'], y=df_chart['tsb'], name="Forme (TSB)",
    marker=dict(color=df_chart['tsb'].apply(lambda x: C_TSB_POS if x >= -10 else C_TSB_NEG)), opacity=0.5
), secondary_y=True)
fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['ctl'], name="Fitness (CTL)", mode='lines',
    line=dict(color=C_CTL, width=4), fill='tozeroy', fillcolor='rgba(37, 99, 235, 0.05)'
), secondary_y=False)
fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['atl'], name="Fatigue (ATL)", mode='lines',
    line=dict(color=C_ATL, width=1, dash='dot'),
), secondary_y=False)

fig_pmc.update_layout(template="simple_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=10, r=10, t=30, b=10), height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), hovermode="x unified")
fig_pmc.update_yaxes(showgrid=False, secondary_y=True, range=[-70, 40])
fig_pmc.update_yaxes(showgrid=True, gridcolor='#e2e8f0', secondary_y=False)

# --- EFFICIENCE ---
df_run = df_chart[df_chart['sport_category'] == 'Run'].copy()
if not df_run.empty:
    fig_eff = px.scatter(df_run, x='start_date_local', y='efficiency_factor', 
                         size='distance_km', color='efficiency_factor', color_continuous_scale='RdYlGn')
    fig_eff.update_layout(template="simple_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0,r=0,t=0,b=0))
    fig_eff.update_coloraxes(showscale=False)
else:
    fig_eff = go.Figure()

# --- BLOC STATS PAR SPORT (NOUVEAU) ---
sport_stats_html = ""
sports_config = [
    {'key': 'Run', 'label': 'Course', 'icon': '🏃', 'color': '#ea580c'},
    {'key': 'Ride', 'label': 'Cyclisme', 'icon': '🚴', 'color': '#0ea5e9'},
    {'key': 'Swim', 'label': 'Natation', 'icon': '🏊', 'color': '#0284c7'},
    {'key': 'Strength', 'label': 'Musculation', 'icon': '🏋️', 'color': '#475569'},
]

html_cards = []

for s in sports_config:
    # Filtrer les données pour ce sport (90 derniers jours)
    df_s = df_chart[df_chart['sport_category'] == s['key']]
    
    count = len(df_s)
    dist = df_s['distance_km'].sum()
    dur_h = df_s['duration_h'].sum()
    elev = df_s['total_elevation_gain'].sum()
    
    # Logique d'affichage spécifique demandée
    if s['key'] == 'Strength':
        # Pour la muscu : Focus sur le nombre de séances
        main_metric = f"{count}"
        main_unit = "SÉANCES"
        sub_metric = f"{int(dur_h)}h totales"
    elif s['key'] == 'Swim':
        # Pour la natation : conversion en mètres si < 5km pour lisibilité
        main_metric = f"{dist:.1f}"
        main_unit = "KM"
        sub_metric = f"{int(dur_h)}h • {count} s."
    else:
        # Run / Ride
        main_metric = f"{int(dist)}"
        main_unit = "KM"
        sub_metric = f"{int(elev)}m D+ • {count} s."

    # Opacité si inactif
    opacity = "1" if count > 0 else "0.4"
    
    card = f"""
    <div class="col-6 col-md-3" style="opacity: {opacity}">
        <div class="card p-3 h-100 border-start border-4" style="border-left-color: {s['color']} !important;">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="fw-bold text-uppercase small text-muted">{s['label']}</span>
                <span style="font-size: 1.2rem;">{s['icon']}</span>
            </div>
            <div class="stat-value">{main_metric} <span style="font-size: 0.9rem; color: #94a3b8; font-weight: 600;">{main_unit}</span></div>
            <div class="small text-muted mt-1">{sub_metric}</div>
        </div>
    </div>
    """
    html_cards.append(card)

sport_stats_html = "".join(html_cards)

# --- TABLEAU ACTIVITÉS ---
last_activities = df.sort_values('start_date_local', ascending=False).head(10)
table_rows = ""
for _, row in last_activities.iterrows():
    icon = "🏃" if row['sport_category'] == 'Run' else "🚴" if row['sport_category'] == 'Ride' else "🏊" if row['sport_category'] == 'Swim' else "🏋️"
    dist = f"{row['distance_km']:.1f} km" if row['distance_km'] > 0 else "-"
    table_rows += f"""
    <tr>
        <td class="py-2 text-nowrap">{icon} {row['start_date_local'].strftime('%d/%m')}</td>
        <td class="fw-bold">{str(row['name'])[:25]}...</td>
        <td>{dist}</td>
        <td><span class="badge border text-dark font-monospace">{int(row['trimp'])}</span></td>
    </tr>
    """

# --- GENERATION HTML ---
html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PERFORMANCE HUB</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: {C_BG}; color: {C_TEXT}; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .card {{ background-color: {C_CARD}; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        .stat-value {{ font-size: 1.8rem; font-weight: 800; line-height: 1.2; }}
        .stat-label {{ color: {C_SUBTEXT}; text-transform: uppercase; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.8px; }}
        .btn-strava {{ background-color: {C_ACCENT}; color: white; font-weight: 700; border-radius: 8px; border: none; }}
        .badge {{ background-color: #f8fafc; color: #475569; }}
    </style>
</head>
<body>
    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h2 class="fw-bold m-0" style="letter-spacing: -1px;">Performance Lab</h2>
                <p class="text-muted small m-0">90 derniers jours | Mis à jour : {last_sync_str}</p>
            </div>
            <button id="syncBtn" class="btn btn-strava px-4 py-2" onclick="triggerSync()">SYNCHRONISER</button>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-6 col-md-3">
                <div class="card p-3 text-center">
                    <div class="stat-label">Fitness (CTL)</div>
                    <div class="stat-value" style="color: {C_CTL}">{current_ctl:.1f}</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card p-3 text-center">
                    <div class="stat-label">Fatigue (ATL)</div>
                    <div class="stat-value" style="color: {C_ATL}">{current_atl:.1f}</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card p-3 text-center">
                    <div class="stat-label">Forme (TSB)</div>
                    <div class="stat-value" style="color: {C_TEXT}">{current_tsb:.1f}</div>
                </div>
            </div>
            <div class="col-6 col-md-3">
                <div class="card p-3 text-center">
                    <div class="stat-label">Ramp Rate</div>
                    <div class="stat-value text-muted">{ramp_rate:+.1f}</div>
                </div>
            </div>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-lg-8">
                <div class="card p-3 h-100">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Charge d'Entraînement</h6>
                    {fig_pmc.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
            </div>
            <div class="col-lg-4">
                 <div class="card p-3 h-100">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Efficience (Run)</h6>
                    {fig_eff.to_html(full_html=False, include_plotlyjs=False)}
                    <div class="mt-auto pt-3 text-center">
                         <h5 class="fw-bold {status_class} mb-0">{status_text}</h5>
                    </div>
                </div>
            </div>
        </div>

        <h6 class="text-muted fw-bold text-uppercase small mb-3">Répartition du Volume (90j)</h6>
        <div class="row g-3 mb-4">
            {sport_stats_html}
        </div>

        <div class="card p-3">
            <h6 class="fw-bold mb-3 border-bottom pb-2">Dernières Activités</h6>
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <tbody>{table_rows}</tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        function triggerSync() {{
            const btn = document.getElementById('syncBtn');
            btn.disabled = true; btn.innerText = "⏳ ...";
            fetch('{SYNC_ENDPOINT}').then(() => {{ 
                alert("Sync OK."); setTimeout(() => location.reload(), 2000); 
            }}).catch(() => {{ alert("Erreur."); btn.disabled = false; }});
        }}
    </script>
</body>
</html>
"""

with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f"✅ Dashboard généré avec succès : {OUTPUT_HTML}")