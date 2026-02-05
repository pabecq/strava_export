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
SYNC_ENDPOINT = "refresh.php"

# PALETTE PROFESSIONNELLE (Light Mode)
C_BG = "#f1f5f9"
C_CARD = "#ffffff"
C_TEXT = "#0f172a"
C_SUBTEXT = "#64748b"
C_CTL = "#2563eb"       # Fitness
C_ATL = "#e11d48"       # Fatigue
C_TSB_POS = "#10b981"   # Forme +
C_TSB_NEG = "#f59e0b"   # Forme -
C_ACCENT = "#fc4c02"

# Specific Sport Colors
C_RUN = '#ea580c'
C_RIDE = '#0ea5e9'

# --- CHARGEMENT & NORMALISATION ---
if not DATA_FILE.exists():
    print("❌ Données introuvables. Lancez d'abord analyse.py")
    exit()

df = pd.read_csv(DATA_FILE)

# Correction du bug de Timezone
df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
df['start_date_local'] = pd.to_datetime(df['start_date_local']).dt.tz_localize(None)

# --- PREPARATION DES DONNEES ---
now = datetime.datetime.now()
current_year = now.year
prev_year = current_year - 1

# 1. Dataset 90 jours (Pour PMC & Stats rapides)
cutoff_date = now - datetime.timedelta(days=90)
df_chart = df[df['date'] >= cutoff_date].sort_values('date').copy()

# 2. Dataset Complet (Pour YoY) - On garde tout df

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

# ==============================================================================
# 1. GRAPHIQUE PMC (EXISTANT)
# ==============================================================================
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
    margin=dict(l=10, r=10, t=30, b=10), height=350, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), hovermode="x unified")
fig_pmc.update_yaxes(showgrid=False, secondary_y=True, range=[-70, 40])
fig_pmc.update_yaxes(showgrid=True, gridcolor='#e2e8f0', secondary_y=False)


# ==============================================================================
# 2. GRAPHIQUE YOY (NOUVEAU)
# ==============================================================================
# Fonction helper pour générer les données cumulées denses (J1 à J365)
def get_cumulative_data(dataframe, sport_type, target_year):
    # Filtrer par sport et année
    df_s = dataframe[(dataframe['sport_category'] == sport_type) & (dataframe['year'] == target_year)].copy()
    if df_s.empty:
        return pd.Series(0, index=range(1, 367))
    
    # Grouper par jour de l'année et sommer la distance
    daily = df_s.groupby('day_of_year')['distance_km'].sum()
    
    # Reindexer pour avoir tous les jours (1 à 366)
    daily = daily.reindex(range(1, 367), fill_value=0)
    
    # Cumulatif
    return daily.cumsum()

# Création des subplots côte à côte
fig_yoy = make_subplots(
    rows=1, cols=2, 
    subplot_titles=("🏃 Course à pied (Annuel)", "🚴 Cyclisme (Annuel)"),
    horizontal_spacing=0.1
)

sports_map = [
    {'sport': 'Run', 'col': 1, 'color': C_RUN},
    {'sport': 'Ride', 'col': 2, 'color': C_RIDE}
]

for s in sports_map:
    # Année Précédente (Ligne pointillée, moins visible)
    y_prev = get_cumulative_data(df, s['sport'], prev_year)
    fig_yoy.add_trace(go.Scatter(
        x=y_prev.index, y=y_prev.values,
        name=f"{prev_year}", mode='lines',
        line=dict(color=s['color'], width=2, dash='dot'),
        opacity=0.5,
        legendgroup=f"group_{s['sport']}",
        showlegend=False
    ), row=1, col=s['col'])

    # Année Courante (Ligne pleine, grasse)
    y_curr = get_cumulative_data(df, s['sport'], current_year)
    
    # Couper la ligne courante à aujourd'hui pour ne pas afficher une ligne plate jusqu'en décembre
    day_of_year_now = now.timetuple().tm_yday
    y_curr = y_curr[y_curr.index <= day_of_year_now]

    fig_yoy.add_trace(go.Scatter(
        x=y_curr.index, y=y_curr.values,
        name=f"{current_year}", mode='lines',
        line=dict(color=s['color'], width=4),
        legendgroup=f"group_{s['sport']}",
        showlegend=False
    ), row=1, col=s['col'])

fig_yoy.update_layout(
    template="simple_white", 
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    height=300, 
    margin=dict(l=10, r=10, t=30, b=10),
    hovermode="x unified"
)
fig_yoy.update_xaxes(showgrid=False, title_text="Jour de l'année")
fig_yoy.update_yaxes(showgrid=True, gridcolor='#e2e8f0', title_text="km")


# ==============================================================================
# 3. EFFICIENCE & RESTE DU DASHBOARD
# ==============================================================================
df_run = df_chart[df_chart['sport_category'] == 'Run'].copy()
if not df_run.empty:
    fig_eff = px.scatter(df_run, x='start_date_local', y='efficiency_factor', 
                         size='distance_km', color='efficiency_factor', color_continuous_scale='RdYlGn')
    fig_eff.update_layout(template="simple_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0,r=0,t=0,b=0))
    fig_eff.update_coloraxes(showscale=False)
else:
    fig_eff = go.Figure()

# --- BLOC STATS PAR SPORT ---
sport_stats_html = ""
sports_config = [
    {'key': 'Run', 'label': 'Course', 'icon': '🏃', 'color': C_RUN},
    {'key': 'Ride', 'label': 'Cyclisme', 'icon': '🚴', 'color': C_RIDE},
    {'key': 'Swim', 'label': 'Natation', 'icon': '🏊', 'color': '#0284c7'},
    {'key': 'Strength', 'label': 'Musculation', 'icon': '🏋️', 'color': '#475569'},
]

html_cards = []

for s in sports_config:
    df_s = df_chart[df_chart['sport_category'] == s['key']]
    count = len(df_s)
    dist = df_s['distance_km'].sum()
    dur_h = df_s['duration_h'].sum()
    elev = df_s['total_elevation_gain'].sum()
    
    if s['key'] == 'Strength':
        main_metric = f"{count}"
        main_unit = "SÉANCES"
        sub_metric = f"{int(dur_h)}h totales"
    elif s['key'] == 'Swim':
        main_metric = f"{dist:.1f}"
        main_unit = "KM"
        sub_metric = f"{int(dur_h)}h • {count} s."
    else:
        main_metric = f"{int(dist)}"
        main_unit = "KM"
        sub_metric = f"{int(elev)}m D+ • {count} s."

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
            <div class="d-flex gap-2">
                <span class="badge d-flex align-items-center p-2 text-secondary" style="font-weight: 600;">
                    <span style="color: {C_RUN}; font-size: 1.2em; margin-right:5px;">●</span> {current_year}
                    <span style="color: {C_RUN}; opacity: 0.5; font-size: 1.2em; margin-left: 10px; margin-right:5px;">●</span> {prev_year}
                </span>
                <button id="syncBtn" class="btn btn-strava px-4 py-2" onclick="triggerSync()">SYNCHRONISER</button>
            </div>
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
            <div class="col-12">
                <div class="card p-3 h-100">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Charge d'Entraînement (PMC)</h6>
                    {fig_pmc.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
            </div>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-12">
                <div class="card p-3">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Comparatif Annuel ({prev_year} vs {current_year})</h6>
                    {fig_yoy.to_html(full_html=False, include_plotlyjs=False)}
                </div>
            </div>
        </div>

        <div class="row g-3 mb-4">
             <div class="col-lg-8">
                 <div class="card p-3 h-100">
                    <h6 class="fw-bold mb-3 border-bottom pb-2">Efficience (Run)</h6>
                    {fig_eff.to_html(full_html=False, include_plotlyjs=False)}
                 </div>
            </div>
            <div class="col-lg-4">
                 <div class="card p-3 h-100 d-flex flex-column justify-content-center text-center">
                      <h6 class="text-muted text-uppercase mb-2">Statut Actuel</h6>
                      <h3 class="fw-bold {status_class} mb-0">{status_text}</h3>
                      <p class="text-muted small mt-2">Basé sur le TSB ({current_tsb:.1f})</p>
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