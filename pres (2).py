import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import uuid

# Initialize the Dash app
app = dash.Dash(__name__, assets_folder='assets/')

# Define severity levels and status descriptions
severity_levels = {
    "EM": (14, "red"), "EM1": (13, "red"), "EM2": (12, "red"), "EM3": (11, "red"),
    "UM": (10, "orange"), "PM1": (9, "yellow"), "PM2": (8, "green"), "PM3": (7, "green"),
    "PM4": (6, "green"), "NSV": (5, "blue"), "TFP": (4, "blue"), "MON": (3, "blue"),
    "FXD": (2, "gray"), "NID": (1, "gray"), "LCR": (0, "gray")
}

status_descriptions = {
    "EM": "Emergency Maintenance - Immediate action required",
    "EM1": "Must be fixed or made safe while on site.",
    "EM2": "Must be made safe and fixed within 2 days.",
    "EM3": "Must be made safe and fixed within 30 days.",
    "UM": "Must be completed within 3 months of notification.",
    "PM1": "Must be completed within 6 months.",
    "PM2": "Must be completed within 12 months depending on rating.",
    "PM3": "Must be completed within 4 years depending on rating.",
    "PM4": "Must be completed within 10 years depending on rating.",
    "NSV": "Work that can be completed by the next person going to site.",
    "TFP": "Referred to Towers Planning.",
    "TFP / PM3": "Must be completed within 4 years depending on rating.",
    "MON": "Monitor Next Inspection / Site Visit.",
    "FXD": "Issue was fixed while on site.",
    "NID": "Next Inspection Due",
    "LCR": "Life Cycle Refurbishment / Replacement"
}

# Define tower assignments (only first 5 tabs)
tower_assignments = {
    'tab-1': ['TAS004699_STR_1', 'TAS004686_STR_1'],
    'tab-2': ['NT002793_STR_1', 'NT006415_STR_1', 'NT003447_STR_1'],
    'tab-3': ['QLD002720_STR_1', 'QLD002533_STR_1'],
    'tab-4': ['NSW002537_STR_1', 'NSW002494_STR_1'],
    'tab-5': ['QLD007207_STR_1', 'QLD002376_STR_1']
}

# Load dataframes at startup
try:
    corrosion_df = pd.read_csv('corrosion_issues.csv')
    corrosion_df['IssueCreated'] = pd.to_datetime(corrosion_df['IssueCreated'], errors='coerce')
    corrosion_df['StructureInstallationDate'] = pd.to_datetime(corrosion_df['StructureInstallationDate'], errors='coerce')
    corrosion_df['distance_km'] = pd.to_numeric(corrosion_df['distance_km'], errors='coerce')
    corrosion_df['RiskRating_Cleaned'] = corrosion_df['RiskRating'].str.split(' - ').str[1].fillna('Unknown').replace({
        'TFP / PM3': 'PM3',
        'PM1 / SMB': 'PM1',
        'PM4 / NSV': 'PM4',
        'TFP / EM3': 'EM3',
        'Unknown': 'NID'
    })
    corrosion_df['Severity'] = corrosion_df['RiskRating_Cleaned'].map(lambda x: severity_levels.get(x, severity_levels['NID'])[0])
    corrosion_df['Color'] = corrosion_df['RiskRating_Cleaned'].map(lambda x: severity_levels.get(x, severity_levels['NID'])[1])
except FileNotFoundError:
    corrosion_df = pd.DataFrame()
    print("Warning: corrosion_issues.csv not found.")

try:
    silo_df = pd.read_csv('silo.csv')
    silo_df['Rain'] = pd.to_numeric(silo_df['Rain'], errors='coerce')
    silo_df['Date2'] = pd.to_datetime(silo_df['Date2'], errors='coerce')
except FileNotFoundError:
    silo_df = pd.DataFrame()
    print("Warning: silo.csv not found.")

# Custom HTML index for dark theme with Roboto font
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body {
                margin: 0;
                padding: 0;
                background-color: black;
                font-family: 'Roboto', sans-serif;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

app.layout = html.Div(
    style={
        'backgroundColor': '#000000',
        'color': '#FFFFFF',
        'font-family': 'Roboto, sans-serif',
        'height': '98vh',
        'width': '100vw',
        'padding': '0',
        'boxSizing': 'border-box',
        'display': 'flex',
        'flexDirection': 'column'
    },
    children=[
        dcc.Tabs(
            id="tabs",
            value='tab-1',
            children=[
                dcc.Tab(
                    label=f'Tab {i+1}',
                    value=f'tab-{i+1}',
                    style={
                        'backgroundColor': '#1a1a1a',
                        'color': '#FFFFFF',
                        'border': 'none',
                        'padding': '8px',
                        'fontSize': '0.9rem',
                        'width': '20%',
                        'textAlign': 'center',
                        'font-family': 'Roboto, sans-serif'
                    },
                    selected_style={
                        'backgroundColor': '#333333',
                        'color': '#FFFFFF',
                        'border': 'none',
                        'padding': '8px',
                        'fontSize': '0.9rem',
                        'width': '20%',
                        'textAlign': 'center',
                        'font-family': 'Roboto, sans-serif'
                    }
                ) for i in range(5)
            ],
            style={
                'border': 'none',
                'backgroundColor': '#000000',
                'width': '100vw',
                'height': '40px',
                'display': 'flex',
                'justifyContent': 'space-between',
                'font-family': 'Roboto, sans-serif'
            }
        ),
        dcc.Loading(
            id="loading",
            type="circle",
            color="#FFFFFF",
            children=[
                html.Div(
                    id='tab-content-container',
                    style={
                        'display': 'flex',
                        'flexDirection': 'row',
                        'width': '100vw',
                        'height': 'calc(98vh - 40px)',
                        'gap': '2px',
                        'padding': '2px',
                        'boxSizing': 'border-box',
                        'font-family': 'Roboto, sans-serif'
                    },
                    children=[
                        html.Div(
                            id='map-container',
                            style={
                                'display': 'flex',
                                'flexDirection': 'column',
                                'width': '33.33vw',
                                'height': 'calc(98vh - 40px)',
                                'gap': '2px',
                                'font-family': 'Roboto, sans-serif'
                            },
                            children=[
                                html.Div(
                                    id='tabs-content-maps',
                                    style={
                                        'padding': '2px',
                                        'backgroundColor': '#1a1a1a',
                                        'borderRadius': '8px',
                                        'width': '33.33vw',
                                        'height': 'calc(98vh - 40px)',
                                        'overflow': 'hidden',
                                        'display': 'flex',
                                        'flexDirection': 'column',
                                        'gap': '2px',
                                        'boxSizing': 'border-box',
                                        'font-family': 'Roboto, sans-serif'
                                    }
                                )
                            ]
                        ),
                        html.Div(
                            id='satellite-container',
                            style={
                                'display': 'flex',
                                'flexDirection': 'column',
                                'width': '33.33vw',
                                'height': 'calc(98vh - 40px)',
                                'gap': '2px',
                                'font-family': 'Roboto, sans-serif'
                            },
                            children=[
                                html.Div(
                                    id='satellite-maps',
                                    style={
                                        'padding': '2px',
                                        'backgroundColor': '#1a1a1a',
                                        'borderRadius': '8px',
                                        'width': '33.33vw',
                                        'height': '100%',
                                        'overflow': 'hidden',
                                        'boxSizing': 'border-box',
                                        'font-family': 'Roboto, sans-serif'
                                    }
                                )
                            ]
                        ),
                        html.Div(
                            id='weather-container',
                            style={
                                'display': 'flex',
                                'flexDirection': 'column',
                                'width': '33.34vw',
                                'height': 'calc(98vh - 40px)',
                                'gap': '2px',
                                'font-family': 'Roboto, sans-serif'
                            },
                            children=[
                                html.Div(
                                    id='tabs-content-weather',
                                    style={
                                        'padding': '2px',
                                        'backgroundColor': '#1a1a1a',
                                        'borderRadius': '8px',
                                        'width': '33.34vw',
                                        'height': '100%',
                                        'overflow': 'hidden',
                                        'boxSizing': 'border-box',
                                        'font-family': 'Roboto, sans-serif'
                                    }
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]
)

# Haversine formula to calculate distance between two lat/lon points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def create_weather_plot(tower, silo_df, corrosion_df, start_date):
    df = silo_df[silo_df['AMSAssetRef'] == tower].copy()
    if df.empty:
        return go.Figure()

    df['Year'] = df['Date2'].dt.year
    df['Month'] = df['Date2'].dt.month
    df['YearMonth'] = df['Date2'].dt.to_period('M')

    monthly_avg = df.groupby('YearMonth').agg({'Rain': 'mean'}).reset_index()
    monthly_avg['Date'] = monthly_avg['YearMonth'].dt.to_timestamp()
    seasonal_avg = df.groupby('Month').agg({'Rain': 'mean'}).reset_index()

    years = range(int(start_date.year), int(df['Year'].max()) + 2)
    seasonal_data = []
    for year in years:
        for month in range(1, 13):
            seasonal_data.append({
                'Date': pd.to_datetime(f'{year}-{month}-01'),
                'Month': month,
                'Seasonal_Rain': seasonal_avg.loc[seasonal_avg['Month'] == month, 'Rain'].iloc[0] if month in seasonal_avg['Month'].values else 0,
            })
    seasonal_df = pd.DataFrame(seasonal_data)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly_avg['Date'],
            y=monthly_avg['Rain'],
            name='Monthly Avg Rainfall (mm)',
            marker_color='#4169E1',
            opacity=0.8,
            showlegend=False
        )
    )

    fig.add_trace(
        go.Scatter(
            x=seasonal_df['Date'],
            y=seasonal_df['Seasonal_Rain'],
            name='Seasonal Avg Rainfall',
            line=dict(color='red', dash='dot', width=2),
            showlegend=False
        )
    )

    tower_corrosion_df = corrosion_df[corrosion_df['AMSAssetRef'] == tower]
    max_rain = monthly_avg['Rain'].max() * 1.2 if not monthly_avg['Rain'].empty else 100
    for _, row in tower_corrosion_df.iterrows():
        issue_date = row['IssueCreated']
        status = row['RiskRating_Cleaned']
        if pd.notna(issue_date):
            fig.add_shape(
                type="line",
                x0=issue_date,
                x1=issue_date,
                y0=0,
                y1=max_rain,
                line=dict(color="yellow", width=3, dash='dot')
            )
            fig.add_annotation(
                x=issue_date + pd.Timedelta(days=15),
                y=max_rain,
                text=f"{issue_date.strftime('%Y-%m-%d')}<br>Status: {status}",
                showarrow=False,
                xanchor='left',
                yanchor='top',
                font=dict(size=8, color='white', family='Roboto, sans-serif')
            )

    fig.update_xaxes(
        range=[start_date, '2025-06-01'],
        tickformat='%Y-%m',
        gridcolor='gray',
        tickangle=45,
        tickfont=dict(size=8, family='Roboto, sans-serif')
    )

    fig.update_yaxes(
        title_text='Rainfall (mm)',
        title_font=dict(color='#4169E1', size=10, family='Roboto, sans-serif'),
        tickfont=dict(color='#4169E1', size=8, family='Roboto, sans-serif'),
        gridcolor='gray'
    )

    fig.update_layout(
        plot_bgcolor='rgb(30, 30, 30)',
        paper_bgcolor='rgb(30, 30, 30)',
        font=dict(color='white', size=8, family='Roboto, sans-serif'),
        margin=dict(l=30, r=30, t=50, b=30),
        showlegend=False
    )

    return fig

def create_severity_plot(tower, corrosion_df, start_date):
    tower_df = corrosion_df[corrosion_df['AMSAssetRef'] == tower].copy()
    if tower_df.empty:
        return go.Figure()

    max_severity = max(severity_levels[sev][0] for sev in severity_levels)
    start_date_corrosion = '2003-01-01'
    global_end_date = '2025-06-01'

    fig = go.Figure()
    for severity in tower_df['RiskRating_Cleaned'].unique():
        severity_df = tower_df[tower_df['RiskRating_Cleaned'] == severity]
        fig.add_trace(
            go.Scatter(
                x=severity_df['IssueCreated'],
                y=severity_df['Severity'],
                mode='markers+text',
                marker=dict(size=10, color=severity_levels.get(severity, severity_levels['NID'])[1],
                            line=dict(width=1, color=severity_levels.get(severity, severity_levels['NID'])[1])),
                text=severity_df['RiskRating_Cleaned'],
                textposition='top center',
                textfont=dict(size=8, family='Roboto, sans-serif'),
                name=f"{severity} - {status_descriptions.get(severity, 'Unknown')}",
                showlegend=False
            )
        )

    for issue_date in tower_df['IssueCreated']:
        if pd.notna(issue_date):
            fig.add_shape(
                type="line",
                x0=issue_date,
                x1=issue_date,
                y0=0,
                y1=max_severity * 1.2,
                line=dict(color="red", width=2)
            )
            fig.add_annotation(
                x=issue_date,
                y=0,
                text=issue_date.strftime('%Y-%m-%d'),
                showarrow=True,
                xanchor='center',
                yanchor='bottom',
                textangle=90,
                font=dict(size=8, color='white', family='Roboto, sans-serif')
            )

    tower_info = tower_df.groupby('AMSAssetRef').agg({
        'StructureInstallationDate': 'first'
    }).reset_index()
    install_date = tower_info['StructureInstallationDate'].iloc[0]
    if pd.notna(install_date):
        fig.add_shape(
            type="line",
            x0=install_date,
            x1=install_date,
            y0=0,
            y1=max_severity * 1.2,
            line=dict(color="white", width=2, dash="dash")
        )
        fig.add_annotation(
            x=install_date,
            y=0,
            text=install_date.strftime('%Y-%m-%d'),
            showarrow=True,
            xanchor='center',
            yanchor='bottom',
            textangle=90,
            font=dict(size=8, color='white', family='Roboto, sans-serif')
        )

    fig.update_xaxes(
        range=[start_date_corrosion, global_end_date],
        gridcolor='lightgrey',
        zerolinecolor='lightgrey',
        tickangle=45,
        tickfont=dict(size=8, family='Roboto, sans-serif')
    )
    fig.update_yaxes(
        range=[0, max_severity * 1.3],
        tickvals=[v[0] for v in severity_levels.values()],
        ticktext=list(severity_levels.keys()),
        gridcolor='lightgrey',
        zerolinecolor='lightgrey',
        title_text="Severity Level",
        title_font=dict(color='white', size=10, family='Roboto, sans-serif'),
        tickfont=dict(color='white', size=8, family='Roboto, sans-serif')
    )

    fig.update_layout(
        plot_bgcolor='rgb(30, 30, 30)',
        paper_bgcolor='rgb(30, 30, 30)',
        font=dict(color='white', size=8, family='Roboto, sans-serif'),
        margin=dict(l=30, r=30, t=30, b=30),
        showlegend=False
    )

    return fig

def create_satellite_figure(lat, lon, height, asset_ref="Selected Location", zoom=17):
    MAPBOX_SATELLITE_TOKEN = 'pk.eyJ1IjoiYW51YmhhdmpldGxleSIsImEiOiJjbWFraHpzbmkwOHRlMmtvaDhhaDY1ajM0In0.MolCp0Po3LjGf8z5ebKJig'

    asset_df = pd.DataFrame({
        'Latitude': [lat],
        'Longitude': [lon],
        'AMSAssetRef': [asset_ref]
    })

    fig = px.scatter_mapbox(
        asset_df,
        lat='Latitude',
        lon='Longitude',
        hover_name='AMSAssetRef',
        zoom=zoom,
        color_discrete_sequence=['red'],
    )

    fig.update_traces(marker=dict(size=14))

    height = max(float(height), 10)
    radius_in_km = height / 1000
    radius_in_degrees = radius_in_km / 111

    num_points = 50
    circle_lat = [lat + radius_in_degrees * np.cos(2 * np.pi * i / num_points)
                  for i in range(num_points + 1)]
    circle_lon = [lon + radius_in_degrees * np.sin(2 * np.pi * i / num_points) / np.cos(lat * np.pi / 180)
                  for i in range(num_points + 1)]

    fig.add_trace(go.Scattermapbox(
        lat=circle_lat,
        lon=circle_lon,
        mode='lines',
        line=dict(width=2, color='yellow'),
        name=f'Fall Zone ({height}m)',
        fill='toself',
        fillcolor='rgba(255, 255, 0, 0.2)',
        textfont=dict(size=18),
    ))

    num_radials = 8
    for i in range(num_radials):
        angle = 2 * np.pi * i / num_radials
        end_lat = lat + radius_in_degrees * np.cos(angle)
        end_lon = lon + radius_in_degrees * np.sin(angle) / np.cos(lat * np.pi / 180)
        fig.add_trace(go.Scattermapbox(
            lat=[lat, end_lat],
            lon=[lon, end_lon],
            mode='lines',
            line=dict(width=1, color='yellow'),
            name='Radial' if i == 0 else None,
            showlegend=False,
        ))

    fig.update_layout(
        mapbox=dict(
            accesstoken=MAPBOX_SATELLITE_TOKEN,
            style='mapbox://styles/mapbox/satellite-v9',
            center=dict(lat=lat, lon=lon),
            zoom=zoom,
            pitch=55,
        ),
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        font_color='#FFFFFF',
        margin={'l': 0, 'r': 0, 't': 0, 'b': 0},  # Reduced top margin to minimize spacing
        showlegend=True,
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor='rgba(0,0,0,0.5)',
            font=dict(color='white', size=14),
        )
    )

    return fig

@app.callback(
    Output('tabs-content-maps', 'children'),
    [Input('tabs', 'value')]
)
def render_map_content(tab):
    towers_selected = list(set(tower_assignments.get(tab, [])))
    if not towers_selected:
        return html.Div([
            html.P('No towers assigned for this tab.', style={'fontSize': '0.9rem', 'font-family': 'Roboto, sans-serif'}),
        ])

    if corrosion_df.empty:
        return html.Div([
            html.P('No corrosion data available.', style={'fontSize': '0.9rem', 'font-family': 'Roboto, sans-serif'}),
        ])

    df = corrosion_df[corrosion_df['AMSAssetRef'].isin(towers_selected)]
    unique_df = df.drop_duplicates(subset=['AMSAssetRef'])

    if df.empty or unique_df.empty:
        return html.Div([
            html.P(f'No corrosion data available for towers: {", ".join(towers_selected)}', style={'fontSize': '0.9rem', 'font-family': 'Roboto, sans-serif'}),
        ])

    # Create dark map with red lines, distance annotations, and distance to coast
    dark_map = go.Figure()
    dark_map.add_trace(
        go.Scattermapbox(
            lat=unique_df['Latitude'],
            lon=unique_df['Longitude'],
            text=[f"{row['AMSAssetRef']}<br>{row['distance_km']:.2f} km to coast" if pd.notna(row['distance_km']) else f"{row['AMSAssetRef']}<br>Unknown distance"
                  for _, row in unique_df.iterrows()],
            mode='markers+text',
            marker=dict(size=8, color='yellow'),
            textfont=dict(color='white', size=10, family='Roboto, sans-serif'),
            textposition='top center',
            showlegend=False
        )
    )

    # Add red lines and distance annotations between tower pairs
    for i, asset1 in enumerate(towers_selected):
        asset1_df = unique_df[unique_df['AMSAssetRef'] == asset1]
        if asset1_df.empty:
            continue
        lat1, lon1 = asset1_df['Latitude'].iloc[0], asset1_df['Longitude'].iloc[0]
        for asset2 in towers_selected[i+1:]:
            asset2_df = unique_df[unique_df['AMSAssetRef'] == asset2]
            if asset2_df.empty:
                continue
            lat2, lon2 = asset2_df['Latitude'].iloc[0], asset2_df['Longitude'].iloc[0]
            distance = haversine(lat1, lon1, lat2, lon2)
            dark_map.add_trace(
                go.Scattermapbox(
                    lat=[lat1, lat2],
                    lon=[lon1, lon2],
                    mode='lines',
                    line=dict(width=2, color='red'),
                    showlegend=False
                )
            )
            mid_lat = (lat1 + lat2) / 2
            mid_lon = (lon1 + lon2) / 2
            dark_map.add_trace(
                go.Scattermapbox(
                    lat=[mid_lat],
                    lon=[mid_lon],
                    mode='text',
                    text=[f"{round(distance, 2)} km"],
                    textfont=dict(color='white', size=8, family='Roboto, sans-serif'),
                    textposition='middle center',
                    showlegend=False
                )
            )

    dark_map.update_layout(
        mapbox=dict(
            style='dark',
            zoom=10,
            center=dict(lat=unique_df['Latitude'].mean(), lon=unique_df['Longitude'].mean()),
            accesstoken='pk.eyJ1IjoiYW51YmhhdmpldGxleSIsImEiOiJjbWFraHpzbmkwOHRlMmtvaDhhaDY1ajM0In0.MolCp0Po3LjGf8z5ebKJig',
        ),
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        font=dict(color='#FFFFFF', family='Roboto, sans-serif'),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False
    )

    return html.Div([
        dcc.Graph(
            figure=dark_map,
            style={'width': '100%', 'height': 'calc(98vh - 40px)'}
        )
    ])

@app.callback(
    Output('satellite-maps', 'children'),
    [Input('tabs', 'value')]
)
def render_satellite_maps(tab):
    towers_selected = list(set(tower_assignments.get(tab, [])))
    if not towers_selected or corrosion_df.empty:
        return html.P('No towers or data available.', style={'fontSize': '0.9rem', 'color': '#FFFFFF', 'font-family': 'Roboto, sans-serif'})

    df = corrosion_df[corrosion_df['AMSAssetRef'].isin(towers_selected)]
    unique_df = df.drop_duplicates(subset=['AMSAssetRef'])

    satellite_maps = []
    for asset in towers_selected:
        asset_df = unique_df[unique_df['AMSAssetRef'] == asset]
        if asset_df.empty:
            satellite_maps.append(
                html.Div([
                    html.H4(asset, style={'margin': '0 0 2px 0', 'fontSize': '1rem', 'fontWeight': 'bold', 'textAlign': 'center', 'font-family': 'Roboto, sans-serif'}),
                    html.P(f'No data for {asset}', style={'color': 'white', 'margin': '2px', 'textAlign': 'center', 'font-family': 'Roboto, sans-serif'})
                ])
            )
            continue
        fig = create_satellite_figure(
            lat=asset_df['Latitude'].iloc[0],
            lon=asset_df['Longitude'].iloc[0],
            height=asset_df['Height'].iloc[0],
            asset_ref=asset,
            zoom=17
        )
        satellite_maps.append(
            html.Div([
                html.H4(asset, style={'margin': '0 0 2px 0', 'fontSize': '1rem', 'fontWeight': 'bold', 'textAlign': 'center', 'font-family': 'Roboto, sans-serif'}),
                dcc.Graph(
                    figure=fig,
                    style={'width': '100%', 'height': f'calc((98vh - 40px - 30px) / {len(towers_selected)})', 'margin': '0'}
                )
            ])
        )

    return html.Div(
        satellite_maps,
        style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px', 'width': '33.33vw', 'height': '100%', 'font-family': 'Roboto, sans-serif'}
    )

@app.callback(
    Output('tabs-content-weather', 'children'),
    [Input('tabs', 'value')]
)
def render_weather_content(tab):
    towers_selected = list(set(tower_assignments.get(tab, [])))
    if not towers_selected or corrosion_df.empty:
        return html.P('No towers or data available.', style={'fontSize': '0.9rem', 'color': '#FFFFFF', 'font-family': 'Roboto, sans-serif'})

    df = corrosion_df[corrosion_df['AMSAssetRef'].isin(towers_selected)]
    if df.empty:
        return html.P(f'No corrosion data available for towers: {", ".join(towers_selected)}', style={'fontSize': '0.9rem', 'color': '#FFFFFF', 'font-family': 'Roboto, sans-serif'})

    earliest_issue_date = df['IssueCreated'].min()
    start_date = pd.to_datetime('2003-01-01') if pd.isna(earliest_issue_date) else earliest_issue_date - pd.offsets.YearBegin(5)

    weather_plots = []
    for tower in towers_selected:
        tower_silo = silo_df[silo_df['AMSAssetRef'] == tower]
        if tower_silo.empty:
            weather_plots.append(
                html.P(f'No rainfall data for {tower}', style={'fontSize': '0.9rem', 'color': '#FFFFFF', 'font-family': 'Roboto, sans-serif'})
            )
            continue

        rainfall_fig = create_weather_plot(tower, silo_df, df, start_date)
        rainfall_fig.update_layout(title=dict(text=f"{tower} Rainfall", x=0.5, xanchor='center', font=dict(size=14, family='Roboto, sans-serif')))
        weather_plots.append(
            dcc.Graph(
                figure=rainfall_fig,
                style={'width': '33.34vw', 'height': 'calc(50% - 2px)', 'margin': '2px'}
            )
        )

    return html.Div(
        weather_plots,
        style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px', 'width': '33.34vw', 'height': '100%', 'overflow': 'hidden', 'font-family': 'Roboto, sans-serif'}
    )

if __name__ == '__main__':
    #app.run(host='0.0.0.0',port=8080, debug=True)
    app.run(debug=True)
