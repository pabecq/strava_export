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

# Correction du bug de Timezone : on force tout en 'naive' (sans fuseau)
df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
df['start_date_local'] = pd.to_datetime(df['start_date_local']).dt.tz_localize(None)

# --- FILTRAGE (90 JOURS) ---
# On s'assure que cutoff_date est aussi sans fuseau
now = datetime.datetime.now()
cutoff_date = now - datetime.timedelta(days=90)

# Filtrage pour le graphique uniquement
df_chart = df[df['date'] >= cutoff_date].sort_values('date').copy()

# --- MÉTRIQUES DE PERFORMANCE ---
if not df.empty:
    last_row = df.sort_values('date').iloc[-1]
    current_ctl = last_row.get('ctl', 0)
    current_atl = last_row.get('atl', 0)
    current_tsb = last_row.get('tsb', 0)
    
    # Ramp Rate (Progression sur 7 jours)
    date_7d_ago = last_row['date'] - datetime.timedelta(days=7)
    df_prev = df[df['date'] <= date_7d_ago]
    ramp_rate = current_ctl - df_prev.iloc[-1]['ctl'] if not df_prev.empty else 0
else:
    current_ctl = current_atl = current_tsb = ramp_rate = 0

# LOGIQUE DE STATUT
if current_tsb < -30:
    status_text, status_class = "SURCHARGE (Risque de blessure)", "text-danger"
elif -30 <= current_tsb < -10:
    status_text, status_class = "OPTIMAL (Zone de progression)", "text-success"
elif -10 <= current_tsb < 5:
    status_text, status_class = "MAINTIEN (Zone neutre)", "text-primary"
else:
    status_text, status_class = "TRANSITION (Récupération)", "text-warning"

last_sync_str = now.strftime('%d/%m à %H:%M')

# --- GRAPHIQUE PRINCIPAL (PMC) ---
fig_pmc = make_subplots(specs=[[{"secondary_y": True}]])

fig_pmc.add_trace(go.Bar(
    x=df_chart['date'], y=df_chart['tsb'],
    name="Forme (TSB)",
    marker=dict(color=df_chart['tsb'].apply(lambda x: C_TSB_POS if x >= -10 else C_TSB_NEG)),
    opacity=0.5
), secondary_y=True)

fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['ctl'],
    name="Fitness (CTL)",
    mode='lines',
    line=dict(color=C_CTL, width=4),
    fill='tozeroy', fillcolor='rgba(37, 99, 235, 0.05)'
), secondary_y=False)

fig_pmc.add_trace(go.Scatter(
    x=df_chart['date'], y=df_chart['atl'],
    name="Fatigue (ATL)",
    mode='lines',
    line=dict(color=C_ATL, width=1, dash='dot'),
), secondary_y=False)

fig_pmc.update_layout(
    template="simple_white",
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=10, r=10, t=30, b=10),
    height=400,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified"
)
fig_pmc.update_yaxes(showgrid=False, secondary_y=True, range=[-70, 40])
fig_pmc.update_yaxes(showgrid=True, gridcolor='#e2e8f0', secondary_y=False)

# --- EFFICIENCE ---
df_run = df_chart[df_chart['sport_category'] == 'Run'].copy()
if not df_run.empty:
    fig_eff = px.scatter(df_run, x='start_date_local', y='efficiency_factor', 
                         size='distance_km', color='efficiency_factor',
                         color_continuous_scale='RdYlGn')
    fig_eff.update_layout(template="simple_white", paper_bgcolor='rgba(0,0,0,0)', 
                          plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0,r=0,t=0,b=0))
    fig_eff.update_coloraxes(showscale=False)
else:
    fig_eff = go.Figure()

# --- TABLEAU ---
last_activities = df.sort_values('start_date_local', ascending=False).head(10)
table_rows = ""
for _, row in last_activities.iterrows():
    icon = "🏃" if row['sport_category'] == 'Run' else "🚴" if row['sport_category'] == 'Ride' else "🏋️"
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
        .card {{ background-color: {C_CARD}; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
        .stat-value {{ font-size: 1.8rem; font-weight: 800; line-height: 1.2; }}
        .stat-label {{ color: {C_SUBTEXT}; text-transform: uppercase; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.8px; }}
        .btn-strava {{ background-color: {C_ACCENT}; color: white; font-weight: 700; border-radius: 8px; border: none; transition: 0.2s; }}
        .btn-strava:hover {{ background-color: #e34402; transform: translateY(-1px); color: white; }}
        table {{ font-size: 0.85rem; }}
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

        <div class="row g-3">
            <div class="col-lg-8">
                <div class="card p-3 mb-3">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Evolution Fitness & Forme</h6>
                    {fig_pmc.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
                <div class="card p-3">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Activités Récentes</h6>
                    <div class="table-responsive">
                        <table class="table table-hover align-middle">
                            <tbody>{table_rows}</tbody>
                        </table>
                    </div>
                </div>
            </div>
            <div class="col-lg-4">
                <div class="card p-3 mb-3">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Efficience (Vitesse/FC)</h6>
                    {fig_eff.to_html(full_html=False, include_plotlyjs=False)}
                    <p class="small text-muted mt-2 mb-0" style="font-size: 0.75rem;">Plus le point est haut, plus votre allure est élevée pour une FC basse (progrès cardio).</p>
                </div>
                <div class="card p-4 text-center">
                    <div class="stat-label mb-2">Verdict Physiologique</div>
                    <h5 class="fw-bold {status_class}">{status_text}</h5>
                    <div class="mt-3 p-2 bg-light rounded" style="font-size: 0.8rem; color: #64748b;">
                        Une TSB entre -10 et -30 indique une charge d'entraînement efficace pour progresser.
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function triggerSync() {{
            const btn = document.getElementById('syncBtn');
            btn.disabled = true;
            btn.innerText = "⏳ EN COURS...";
            fetch('{SYNC_ENDPOINT}').then(() => {{ 
                alert("Synchronisation lancée. Rechargement dans 5 secondes."); 
                setTimeout(() => location.reload(), 5000); 
            }}).catch(() => {{
                alert("Erreur lors de la sync.");
                btn.disabled = false;
                btn.innerText = "SYNCHRONISER";
            }});
        }}
    </script>
</body>
</html>
"""

with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f"✅ Dashboard généré avec succès : {OUTPUT_HTML}")