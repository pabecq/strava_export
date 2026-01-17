import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import datetime

# --- CONFIG ---
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / 'output/analytics_strava.csv'
OUTPUT_HTML = Path('/var/www/html/strava_dashboard.html')

# --- LOAD DATA ---
if not DATA_FILE.exists():
    print("❌ Pas de données trouvées.")
    exit()

df = pd.read_csv(DATA_FILE)

# --- FIX TIMEZONE (La correction est ici) ---
# On convertit en date, et SI il y a un fuseau horaire, on le supprime (.tz_localize(None))
df['start_date_local'] = pd.to_datetime(df['start_date_local'])
if df['start_date_local'].dt.tz is not None:
    df['start_date_local'] = df['start_date_local'].dt.tz_localize(None)

df['year'] = df['start_date_local'].dt.year
df['day_of_year'] = df['start_date_local'].dt.dayofyear

# On garde tout pour l'historique, mais on isole l'année en cours
current_year = df['year'].max()
previous_year = current_year - 1
df_current = df[df['year'] == current_year].copy()

# --- KPI CALCULS ---
total_km = df_current['distance_km'].sum()
total_elev = df_current['total_elevation_gain'].sum()
count_runs = len(df_current[df_current['sport_type'].isin(['Run', 'TrailRun'])])
count_rides = len(df_current[df_current['sport_type'].isin(['Ride', 'GravelRide', 'VirtualRide'])])

# --- GRAPHIQUE 1 : LE GHOST RUNNER (Cumulatif Année vs Année) ---
def get_cumulative(year_target):
    # On filtre et on trie
    d = df[df['year'] == year_target].sort_values('day_of_year')
    if d.empty:
        return pd.DataFrame(columns=['day_of_year', 'distance_km'])
    # On groupe par jour
    d = d.groupby('day_of_year')['distance_km'].sum().cumsum().reset_index()
    return d

cumul_curr = get_cumulative(current_year)
cumul_prev = get_cumulative(previous_year)

fig_ghost = go.Figure()
# L'année dernière (Ligne grise pointillée)
if not cumul_prev.empty:
    fig_ghost.add_trace(go.Scatter(
        x=cumul_prev['day_of_year'], y=cumul_prev['distance_km'],
        mode='lines', name=f'{previous_year}',
        line=dict(color='gray', dash='dot')
    ))

# Cette année (Ligne orange épaisse)
if not cumul_curr.empty:
    fig_ghost.add_trace(go.Scatter(
        x=cumul_curr['day_of_year'], y=cumul_curr['distance_km'],
        mode='lines', name=f'{current_year}',
        line=dict(color='#fc4c02', width=4)
    ))
    # Indicateur dernier jour
    last_day = cumul_curr.iloc[-1]
    fig_ghost.add_trace(go.Scatter(
        x=[last_day['day_of_year']], y=[last_day['distance_km']],
        mode='markers+text', 
        text=[f"{last_day['distance_km']:.0f} km"],
        textposition="top left",
        marker=dict(color='#fc4c02', size=10),
        showlegend=False
    ))

fig_ghost.update_layout(
    title="📈 Duel Annuel : Suis-je en avance ?",
    xaxis_title="Jour de l'année",
    yaxis_title="Km Cumulés",
    hovermode="x unified",
    height=400,
    margin=dict(l=20, r=20, t=50, b=20)
)

# --- GRAPHIQUE 2 : VOLUME ROLLING (Consistance) ---
df_run = df[df['sport_type'].isin(['Run', 'TrailRun'])].copy()

if not df_run.empty:
    df_run.set_index('start_date_local', inplace=True)
    # Resample par semaine
    weekly = df_run.resample('W')['distance_km'].sum().reset_index()
    # Rolling average 4 semaines
    weekly['rolling_4w'] = weekly['distance_km'].rolling(4).mean()
    
    # Filtre 12 mois glissants (Maintenant ça marche car tout est "naïf")
    last_12m = weekly[weekly['start_date_local'] > (datetime.datetime.now() - datetime.timedelta(days=365))]

    fig_consist = go.Figure()
    fig_consist.add_trace(go.Bar(
        x=last_12m['start_date_local'], y=last_12m['distance_km'],
        name='Volume Hebdo', marker_color='#ffccbc'
    ))
    fig_consist.add_trace(go.Scatter(
        x=last_12m['start_date_local'], y=last_12m['rolling_4w'],
        name='Moyenne 4 semaines', line=dict(color='#d84315', width=3)
    ))
    fig_consist.update_layout(title="📅 Consistance (Rolling 12 mois)", height=350, showlegend=False)
else:
    fig_consist = go.Figure()
    fig_consist.update_layout(title="Pas assez de données Running")


# --- GRAPHIQUE 3 : EFFICIENCY MATRIX ---
df_eff = df_current[
    (df_current['sport_type'].isin(['Run', 'TrailRun'])) & 
    (df_current['average_heartrate'] > 100) & 
    (df_current['duration_h'] > 0.3)
].copy()

if not df_eff.empty:
    fig_eff = px.scatter(
        df_eff, x='average_heartrate', y='avg_speed_kmh',
        size='distance_km', color='start_date_local',
        title="🫀 Efficiency Check (Plus foncé = Plus récent)",
        labels={'average_heartrate': 'FC Moyenne', 'avg_speed_kmh': 'Vitesse (km/h)'}
    )
    fig_eff.update_layout(height=400)
else:
    fig_eff = go.Figure()
    fig_eff.update_layout(title="Pas assez de données cardio pour l'année en cours")

# --- TABLEAU : DERNIERES ACTIVITES ---
last_5 = df.sort_values('start_date_local', ascending=False).head(5)
last_5_html = ""
for _, row in last_5.iterrows():
    date_str = row['start_date_local'].strftime("%d/%m")
    type_icon = "🏃" if row['sport_type'] in ['Run', 'TrailRun'] else "🚴"
    bpm = int(row['average_heartrate']) if row['average_heartrate'] > 0 else '-'
    last_5_html += f"""
    <tr style="border-bottom: 1px solid #eee;">
        <td style="padding:10px;">{type_icon} <b>{date_str}</b></td>
        <td style="padding:10px;">{str(row['name'])[:20]}...</td>
        <td style="padding:10px;"><b>{row['distance_km']:.1f}</b> km</td>
        <td style="padding:10px;">{row['avg_speed_kmh']:.1f} km/h</td>
        <td style="padding:10px; color:#666;">{bpm} bpm</td>
    </tr>
    """

# --- GENERATION HTML ---
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Strava Pro Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        .header {{ background: white; padding: 20px; border-bottom: 1px solid #ddd; margin-bottom: 30px; }}
        .card {{ border: none; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 25px; overflow: hidden; }}
        .kpi-val {{ font-size: 2.5rem; font-weight: 800; color: #2d3436; letter-spacing: -1px; }}
        .kpi-label {{ font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: #b2bec3; letter-spacing: 1px; }}
        .btn-refresh {{ background-color: #fc4c02; color: white; border: none; padding: 10px 20px; border-radius: 50px; font-weight: bold; text-decoration: none; transition: transform 0.2s; }}
        .btn-refresh:hover {{ transform: scale(1.05); color: white; }}
    </style>
</head>
<body>

    <div class="header">
        <div class="container d-flex justify-content-between align-items-center">
            <div>
                <h2 style="margin:0; font-weight:800;">🔥 Performance Lab</h2>
                <span class="text-muted">Analyse saison {current_year}</span>
            </div>
            <a href="refresh.php" class="btn-refresh">🔄 Sync Data</a>
        </div>
    </div>

    <div class="container">
        
        <div class="row">
            <div class="col-md-3 col-6">
                <div class="card p-4 text-center">
                    <div class="kpi-val">{total_km:,.0f}</div>
                    <div class="kpi-label">Kilomètres</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="card p-4 text-center">
                    <div class="kpi-val">{total_elev:,.0f}</div>
                    <div class="kpi-label">Dénivelé (m)</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="card p-4 text-center">
                    <div class="kpi-val">{count_runs}</div>
                    <div class="kpi-label">Sorties Run</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="card p-4 text-center">
                    <div class="kpi-val">{count_rides}</div>
                    <div class="kpi-label">Sorties Vélo</div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-body">
                        {fig_ghost.to_html(full_html=False, include_plotlyjs='cdn')}
                    </div>
                </div>
                <div class="card">
                    <div class="card-body">
                        {fig_consist.to_html(full_html=False, include_plotlyjs=False)}
                    </div>
                </div>
            </div>
            
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header bg-white font-weight-bold">📅 Dernières Sorties</div>
                    <div class="card-body p-0">
                        <table style="width:100%; font-size:0.9em;">
                            {last_5_html}
                        </table>
                    </div>
                </div>

                <div class="card">
                    <div class="card-body">
                         {fig_eff.to_html(full_html=False, include_plotlyjs=False)}
                    </div>
                </div>
            </div>
        </div>

        <div class="text-center text-muted py-4" style="font-size:0.8em">
            Propulsé par Python & DietPi • Dernière MAJ: {datetime.datetime.now().strftime("%d/%m %H:%M")}
        </div>
    </div>

</body>
</html>
"""

OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"✅ Dashboard PRO généré : {OUTPUT_HTML}")