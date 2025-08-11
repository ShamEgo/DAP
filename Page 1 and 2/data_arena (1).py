import os
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import dash_deck
import pydeck as pdk
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import numpy as np
import openmeteo_requests
import requests_cache
from retry_requests import retry

WEATHER_API_KEY = "KKLV3UDGTSXTVDNYA7N7QMQFG"

# Load structure details data
df = pd.read_excel('Structure Details_17March2025.xlsx', sheet_name='Amplitel Structure Details')
df = df.drop(df[df['StructureAssetStatus'] == 'REMOVED'].index)
df = df.drop(df[df['StructureAssetStatus'] == 'PROPOSED CREATE'].index)
df = df.fillna(0)

# Load maintenance issues data
maintenance_df = pd.read_excel("Structure Maintenance Issues _ 17March2025.xlsx", sheet_name="Maintenance Issues")
maintenance_df['RiskRating_Cleaned'] = maintenance_df['RiskRating'].str.extract(r'-\s*(\w+)')
maintenance_df['IssueCreated'] = pd.to_datetime(maintenance_df['IssueCreated'], errors='coerce')

# Define the columns to keep
selected_columns = [
    'SiteRef', 'AMSAssetRef', 'address_id_tower', 'State', 'SiteName', 
    'StructureClassCode', 'Height', 'HeightExtension', 'WarningLights', 
    'LastInspectionDate', 'ReviewInspectionDate', 'LegacyAssetId', 
    'TelstraAddressID', 'StructureOwnerCompanyName', 'Manufacturer', 
    'Model', 'StructureAssetStatus', 'StructureInstallationDate', 
    'PaintingType', 'ExtensionType', 'TerrainCategoryDescription', 
    'SiteHeightRL', 'AccessRestriction', 'StructureLoadPercentage', 
    'StructureLoadVariance', 'FootingLoadPercentage', 'FoundationLoadVariance', 
    'AnchorTenant', 'LegacyAssetOwner', 'ABSRegion', 'DigitalTwinAvailability', 
    'StreetAddress', 'Town', 'Longitude', 'Latitude', 'CorrosionRegionType', 
    'WindRegionType', 'SnowIceRegion'
]

# Filter the DataFrame
df = df[selected_columns]

# Mapping corrosion region types to numeric values
mapping = {
    'A (Very Low)': 1, 'B (Low)': 2, 'C (Medium)': 3, 'D (High)': 4,
    'E (Very High)': 5, 'F (Inland Tropical)': 6, float('nan'): float('nan')
}
df['corrosion_region_id'] = df['CorrosionRegionType'].map(mapping).astype('Int64')

# Replace NaN values
df = df.dropna(subset=['Longitude', 'Latitude'])
df['Height'] = df['Height'].fillna(0)
df['corrosion_region_id'] = df['corrosion_region_id'].fillna(0)

# Mapping for WindRegionType and SnowIceRegion
wind_mapping = {'A': 1, 'B': 2, 'C': 3, 'D': 4}
df['wind_region_id'] = df['WindRegionType'].map(wind_mapping).fillna(0).astype('Int64')
snow_mapping = {'No': 0, 'Yes': 1}
df['snow_ice_id'] = df['SnowIceRegion'].map(snow_mapping).fillna(0).astype('Int64')

# Define severity levels for maintenance plot
severity_levels = {
    "EM": (14, "red"), "EM1": (13, "red"), "EM2": (12, "red"), "EM3": (11, "red"),  
    "UM": (10, "orange"), "PM1": (9, "yellow"), "PM2": (8, "green"), 
    "PM3": (7, "green"), "PM4": (6, "green"), "NSV": (5, "blue"), 
    "TFP": (4, "blue"), "MON": (3, "blue"), "FXD": (2, "gray"), 
    "NID": (1, "gray"), "LCR": (0, "gray")     
}

# Status descriptions for plot legend
status_descriptions = {
    "EM": "Emergency Maintenance - Immediate action required",
    "EM1": "Must be fixed or made safe while on site",
    "EM2": "Must be made safe and fixed within 2 days",
    "EM3": "Must be made safe and fixed within 30 days",
    "UM": "Must be completed within 3 months",
    "PM1": "Must be completed within 6 months",
    "PM2": "Must be completed within 12 months",
    "PM3": "Must be completed within 4 years",
    "PM4": "Must be completed within 10 years",
    "NSV": "Work for next site visitor",
    "TFP": "Referred to Towers Planning",
    "MON": "Monitor Next Inspection",
    "FXD": "Issue fixed while on site",
    "NID": "Next Inspection Due",
    "LCR": "Life Cycle Refurbishment"
}

# Mapbox access token
MAPBOX_TOKEN = "pk.eyJ1IjoiYW51YmhhdmpldGxleSIsImEiOiJjbThxeDgxanowcnIwMmxxMmJwZmxmdW9tIn0.aHQqo95yX-e1S_eyj93TvA"

# Define the Dash app
app = Dash(__name__)

# Define custom CSS styles
app.css.append_css({
    'external_url': 'https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Roboto&display=swap'
})

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * {
                box-sizing: border-box;
            }
            body {
                margin: 0;
                padding: 0;
                background-color: #333333;
                font-size: 16px;
                overflow-x: hidden;
            }
            .section {
                padding: 0.5rem;
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: 8px;
                overflow: hidden;
                transition: width 0.3s ease, opacity 0.3s ease;
            }
            .table-container tr:hover td {
                background-color: #3a3a3a !important;
                cursor: pointer;
            }
            div[style*="overflow-y: auto"]::-webkit-scrollbar {
                width: 12px;
                background-color: #333333;
            }
            div[style*="overflow-y: auto"]::-webkit-scrollbar-thumb {
                background-color: #4169E1;
                border-radius: 6px;
                border: 2px solid #333333;
            }
            div[style*="overflow-y: auto"]::-webkit-scrollbar-track {
                background-color: #333333;
            }
            h1, h2, h3 {
                font-family: 'Orbitron', sans-serif;
                color: white;
                text-align: center;
                margin: 0.5rem 0;
            }
            .card-container {
                display: grid;
                grid-template-columns: 1fr;
                gap: 0.5rem;
                padding: 0.5rem;
            }
            .card {
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: 8px;
                padding: 0.75rem;
                text-align: center;
                color: #e0e0e0;
                font-family: 'Roboto', sans-serif;
                transition: background-color 0.2s ease;
            }
            .card:hover {
                background-color: #3a3a3a;
                cursor: pointer;
            }
            .card h3 {
                font-weight: 700;
                color: #ffffff;
                margin: 0.5rem 0;
                font-family: 'Orbitron', sans-serif;
            }
            .card p {
                margin: 0.25rem 0;
                font-size: 0.875rem;
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

# Function to create Pydeck layer
def create_layer(category):
    color_expression = {
        'corrosion_region_id': [
            "corrosion_region_id === 1 ? 255 : corrosion_region_id === 2 ? 255 : corrosion_region_id === 3 ? 255 : corrosion_region_id === 4 ? 0 : corrosion_region_id === 5 ? 255 : corrosion_region_id === 6 ? 0 : 50",
            "corrosion_region_id === 1 ? 255 : corrosion_region_id === 2 ? 255 : corrosion_region_id === 3 ? 0 : corrosion_region_id === 4 ? 255 : corrosion_region_id === 5 ? 0 : corrosion_region_id === 6 ? 173 : 50",
            "corrosion_region_id === 1 ? 255 : corrosion_region_id === 2 ? 0 : corrosion_region_id === 3 ? 255 : corrosion_region_id === 4 ? 0 : corrosion_region_id === 5 ? 0 : corrosion_region_id === 6 ? 255 : 50",
            255
        ],
    }
    
    return pdk.Layer(
        'ColumnLayer',
        df,
        pickable=True,
        get_position=['Longitude', 'Latitude'],
        get_elevation='Height',
        elevation_scale=100,
        radius=1000,
        get_fill_color=color_expression[category],
        auto_highlight=True
    )

# Initial layer and deck
initial_layer = create_layer('corrosion_region_id')
view_state = pdk.ViewState(latitude=-25.3, longitude=133.8, zoom=4, bearing=0, pitch=45)
initial_tooltip = {
    "html": "<b>{SiteName}</b><br>Height: {Height}m<br>Corrosion: {CorrosionRegionType}",
    "style": {"background": "grey", "color": "white", "font-family": '"Roboto", sans-serif', "z-index": "10000"}
}
r = pdk.Deck(
    layers=[initial_layer],
    initial_view_state=view_state,
    tooltip=initial_tooltip,
    map_style=pdk.map_styles.DARK
)

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
        margin={'l': 0, 'r': 0, 't': 30, 'b': 0},
        showlegend=True,
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor='rgba(0,0,0,0.5)',
            font=dict(color='white')
        )
    )
    
    return fig

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

def fetch_weather_data(lat, lon, installation_date):
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    start_date = pd.to_datetime(installation_date).strftime('%Y-%m-%d')

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": "2025-07-15",
        "daily": [
            "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
            "wind_speed_10m_max", "wind_speed_10m_mean", "wind_speed_10m_min",
            "wind_gusts_10m_max", "wind_gusts_10m_mean", "wind_gusts_10m_min"
        ],
        "timezone": "Australia/Sydney"
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
    print(f"Elevation {response.Elevation()} m asl")
    print(f"Timezone {response.Timezone()}{response.TimezoneAbbreviation()}")
    print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

    daily = response.Daily()
    daily_data = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        ),
        "temperature_2m_mean": daily.Variables(0).ValuesAsNumpy(),
        "temperature_2m_max": daily.Variables(1).ValuesAsNumpy(),
        "temperature_2m_min": daily.Variables(2).ValuesAsNumpy(),
        "wind_speed_10m_max": daily.Variables(3).ValuesAsNumpy(),
        "wind_speed_10m_mean": daily.Variables(4).ValuesAsNumpy(),
        "wind_speed_10m_min": daily.Variables(5).ValuesAsNumpy(),
        "wind_gusts_10m_max": daily.Variables(6).ValuesAsNumpy(),
        "wind_gusts_10m_mean": daily.Variables(7).ValuesAsNumpy(),
        "wind_gusts_10m_min": daily.Variables(8).ValuesAsNumpy()
    }

    daily_dataframe = pd.DataFrame(data=daily_data)
    return daily_dataframe

def create_weather_plots(weather_df, lat, lon, ams_ref="Selected Location"):
    if weather_df is None or weather_df.empty:
        return html.Div("No weather data available", style={'color': 'white'})
    
    weather_df['date'] = pd.to_datetime(weather_df['date'])
    weather_df = weather_df.set_index('date').resample('ME').mean().reset_index()

    # Temperature Plot (Mean, Max, Min)
    temp_fig = go.Figure()
    temp_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['temperature_2m_mean'],
        mode='lines',
        line=dict(color='rgb(0, 255, 0)'),
        name='Mean Temperature'
    ))
    temp_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['temperature_2m_max'],
        mode='lines',
        line=dict(color='rgb(199, 155, 25)'),
        name='Max Temperature',
        opacity=0.6
    ))
    temp_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['temperature_2m_min'],
        mode='lines',
        line=dict(color='rgb(0, 255, 255)'),
        name='Min Temperature',
        opacity=0.4
    ))
    temp_fig.update_layout(
        title=f'Monthly Temperature: Mean, Max, Min (°C) at {ams_ref}',
        xaxis_title='Date',
        yaxis_title='Temperature (°C)',
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        font=dict(color='white'),
        height=300,
        margin=dict(l=20, r=20, t=30, b=10),
        showlegend=False,
        xaxis=dict(
            tickmode='array',
            tickvals=pd.date_range(start=weather_df['date'].min(), end=weather_df['date'].max(), freq='YS'),
            tickformat='%Y',
            showgrid=False  # Disable x-axis grid
        ),
        yaxis=dict(
            showgrid=False  # Disable y-axis grid
        )
    )

    # Wind Speed Plot (Mean, Max, Min)
    wind_speed_fig = go.Figure()
    wind_speed_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['wind_speed_10m_mean'],
        mode='lines',
        line=dict(color='rgb(255, 0, 255)'),
        name='Mean Wind Speed'
    ))
    wind_speed_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['wind_speed_10m_max'],
        mode='lines',
        line=dict(color='rgb(255, 153, 0)'),
        name='Max Wind Speed',
        opacity=0.6
    ))
    wind_speed_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['wind_speed_10m_min'],
        mode='lines',
        line=dict(color='rgb(0, 255, 153)'),
        name='Min Wind Speed',
        opacity=0.4
    ))
    wind_speed_fig.update_layout(
        title=f'Monthly Wind Speed: Mean, Max, Min (km/h) at {ams_ref}',
        xaxis_title='Date',
        yaxis_title='Wind Speed (km/h)',
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        font=dict(color='white'),
        height=300,
        margin=dict(l=20, r=20, t=30, b=10),
        showlegend=False,
        xaxis=dict(
            tickmode='array',
            tickvals=pd.date_range(start=weather_df['date'].min(), end=weather_df['date'].max(), freq='YS'),
            tickformat='%Y',
            showgrid=False  # Disable x-axis grid
        ),
        yaxis=dict(
            showgrid=False  # Disable y-axis grid
        )
    )

    # Wind Gusts Plot (Mean, Max, Min)
    wind_gusts_fig = go.Figure()
    wind_gusts_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['wind_gusts_10m_mean'],
        mode='lines',
        line=dict(color='rgb(255, 0, 0)'),
        name='Mean Wind Gusts'
    ))
    wind_gusts_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['wind_gusts_10m_max'],
        mode='lines',
        line=dict(color='rgb(255, 102, 102)'),
        name='Max Wind Gusts',
        opacity=0.6
    ))
    wind_gusts_fig.add_trace(go.Scatter(
        x=weather_df['date'],
        y=weather_df['wind_gusts_10m_min'],
        mode='lines',
        line=dict(color='rgb(255, 153, 153)'),
        name='Min Wind Gusts',
        opacity=0.4
    ))
    wind_gusts_fig.update_layout(
        title=f'Monthly Wind Gusts: Mean, Max, Min (km/h) at {ams_ref}',
        xaxis_title='Date',
        yaxis_title='Wind Gusts (km/h)',
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        font=dict(color='white'),
        height=300,
        margin=dict(l=20, r=20, t=30, b=10),
        showlegend=False,
        xaxis=dict(
            tickmode='array',
            tickvals=pd.date_range(start=weather_df['date'].min(), end=weather_df['date'].max(), freq='YS'),
            tickformat='%Y',
            showgrid=False  # Disable x-axis grid
        ),
        yaxis=dict(
            showgrid=False  # Disable y-axis grid
        )
    )

    plots = [
        dcc.Graph(figure=fig, style={'width': '100%', 'margin-bottom': '0.5rem'})
        for fig in [temp_fig, wind_speed_fig, wind_gusts_fig]
    ]
    
    return html.Div(plots, style={'display': 'flex', 'flex-direction': 'column', 'width': '100%'})

app.layout = html.Div([
    html.Div(
        id='legend-container',
        style={
            'position': 'absolute', 'top': '10rem', 'left': '1rem',
            'background-color': 'rgba(0, 0, 0, 0.7)', 'padding': '0.5rem', 'border-radius': '5px',
            'z-index': '10', 'color': 'white', 'font-family': 'Roboto, sans-serif'
        }
    ),
    html.Div(
        id='container',
        children=[
            html.Div(
                id='map-table-container',
                children=[
                    html.Div(
                        id='map-container',
                        children=[
                            dash_deck.DeckGL(
                                id='pydeck-map',
                                data=r.to_json(),
                                tooltip=initial_tooltip,
                                enableEvents=['click'],
                                style={'width': '100%', 'height': '100%', 'position': 'relative'},
                                mapboxKey=MAPBOX_TOKEN
                            ),
                        ],
                        className='section map-section',
                        style={
                            'width': '100%', 'min-width': '100%', 'max-width': '100%', 'height': '100vh',
                            'padding': '0.5rem'
                        }
                    ),
                    html.Div(
                        id='cards-satellite-container',
                        children=[
                            html.Div(
                                id='satellite-container',
                                children=[
                                    dcc.Graph(id='satellite-map', style={'height': '100%', 'width': '100%'})
                                ],
                                className='satellite-container section',
                                style={
                                    'display': 'none', 'height': '45vh', 'width': '50%', 'overflow': 'auto',
                                    'box-sizing': 'border-box', 'background-color': '#1a1a1a', 'border': '2px solid #444',
                                    'border-radius': '8px', 'margin': '0.2rem'
                                }
                            ),
                            html.Div(
                                id='table-container',
                                children=[
                                    html.Div(
                                        id="data-table",
                                        style={'width': '100%', 'height': '100%'}
                                    )
                                ],
                                className='section table-section',
                                style={
                                    'display': 'none', 'width': '50%', 'height': '45vh',
                                    'padding': '0.5rem', 'margin': '0.2rem'
                                }
                            ),
                        ],
                        style={
                            'display': 'none', 'flex-direction': 'row', 'width': '100%',
                            'gap': '0.2rem'
                        }
                    ),
                ],
                className='map-table-container',
                style={
                    'display': 'flex', 'flex-direction': 'column', 'width': '100vw', 'min-width': '100vw',
                    'max-width': '100vw', 'margin': '0', 'padding': '0'
                }
            ),
            html.Div(
                id='side-by-side-container',
                children=[
                    html.Div(
                        id='left-panel-container',
                        children=[
                            html.Div(
                                id='plot-container',
                                children=[
                                    html.H2("Maintenance Issues", style={'font-family': 'Roboto, sans-serif'})
                                ],
                                className='section plot-section',
                                style={
                                    'display': 'none', 'width': '100%', 'height': '50vh',
                                    'padding': '0.5rem', 'overflow-y': 'auto'
                                }
                            ),
                            html.Div(
                                id='digital-twin-container',
                                children=[
                                    html.H2("Digital Twin", style={'font-family': 'Roboto, sans-serif'}),
                                ],
                                className='section digital-twin-section',
                                style={
                                    'display': 'none', 'width': '100%', 'height': '50vh', 'padding': '0.5rem'
                                }
                            )
                        ],
                        style={
                            'display': 'flex', 'flex-direction': 'column',
                            'width': '100%', 'height': '100vh', 'padding': '0.5rem'
                        }
                    ),
                    html.Div(
                        id='weather-container',
                        children=[
                            html.H2("Historical Weather Data", style={'font-family': 'Roboto, sans-serif'}),
                            dcc.Loading(
                                id="loading-weather",
                                type="circle",
                                color="#4169E1",
                                children=html.Div(id='weather-plots')
                            )
                        ],
                        className='weather-container section',
                        style={
                            'display': 'none', 'width': '100%', 'height': '100vh',
                            'overflow': 'auto', 'box-sizing': 'border-box',
                            'background-color': '#1a1a1a', 'border': '2px solid #444', 'border-radius': '8px',
                            'margin': '0.2rem 0'
                        }
                    )
                ],
                className='side-by-side-container',
                style={
                    'display': 'none', 'flex-direction': 'row',
                    'width': '50vw', 'min-width': '50vw', 'max-width': '50vw',
                    'margin': '0', 'padding': '0', 'gap': '0.2rem'
                }
            )
        ],
        className='container',
        style={
            'display': 'flex', 'flex-direction': 'row',
            'width': '100vw', 'min-height': '100vh',
            'margin': '0', 'padding': '0', 'gap': '0', 'overflow-x': 'hidden'
        }
    )
], style={'background-color': 'black', 'min-height': '100vh', 'margin': '0', 'padding': '0'})

@app.callback(
    [Output('map-container', 'style'),
     Output('table-container', 'style'),
     Output('data-table', 'children'),
     Output('plot-container', 'style'),
     Output('plot-container', 'children'),
     Output('satellite-container', 'style'),
     Output('weather-container', 'style'),
     Output('satellite-map', 'figure'),
     Output('digital-twin-container', 'style'),
     Output('side-by-side-container', 'style'),
     Output('map-table-container', 'style'),
     Output('cards-satellite-container', 'style')],
    [Input('pydeck-map', 'clickInfo')]
)
def update_layout(click_info):
    default_map_style = {
        'width': '100%', 'min-width': '100%', 'max-width': '100%', 'height': '100vh',
        'padding': '0.5rem', 'background-color': '#1a1a1a', 'border': '2px solid #444',
        'border-radius': '8px', 'margin': '0.2rem 0', 'position': 'relative'
    }
    default_table_style = {
        'display': 'none', 'width': '50%', 'height': '25vh',
        'padding': '0.5rem', 'margin': '0.2rem'
    }
    default_plot_style = {
        'display': 'none', 'width': '100%', 'height': '50vh',
        'padding': '0.5rem', 'overflow-y': 'auto'
    }
    default_satellite_style = {
        'display': 'none', 'height': '25vh', 'width': '50%', 'overflow': 'auto',
        'box-sizing': 'border-box', 'background-color': '#1a1a1a', 'border': '2px solid #444',
        'border-radius': '8px', 'margin': '0.2rem'
    }
    default_weather_style = {
        'display': 'none', 'width': '100%', 'height': '100vh',
        'overflow': 'auto', 'box-sizing': 'border-box',
        'background-color': '#1a1a1a', 'border': '2px solid #444', 'border-radius': '8px',
        'margin': '0.2rem 0'
    }
    default_digital_twin_style = {
        'display': 'none', 'width': '100%', 'height': '50vh',
        'padding': '0.5rem', 'overflow-y': 'auto'
    }
    default_side_by_side_style = {
        'display': 'none', 'flex-direction': 'row', 'width': '50vw', 'min-width': '50vw',
        'max-width': '50vw', 'margin': '0', 'padding': '0', 'gap': '0.2rem'
    }
    default_map_table_style = {
        'display': 'flex', 'flex-direction': 'column', 'width': '100vw', 'min-width': '100vw',
        'max-width': '100vw', 'margin': '0', 'padding': '0'
    }
    default_cards_satellite_style = {
        'display': 'none', 'flex-direction': 'row', 'width': '100%',
        'gap': '0.2rem'
    }

    if not click_info or 'object' not in click_info:
        return (default_map_style,
                default_table_style,
                html.Div("Click a point on the map to view details.", style={
                    'color': 'white', 'text-align': 'center', 'font-family': 'Roboto, sans-serif',
                    'padding': '1rem'
                }),
                default_plot_style,
                [html.H2("Maintenance Issues", style={'font-family': 'Roboto, sans-serif'})],
                default_satellite_style,
                default_weather_style,
                create_satellite_figure(df['Latitude'].iloc[0], df['Longitude'].iloc[0], 0),
                default_digital_twin_style,
                default_side_by_side_style,
                default_map_table_style,
                default_cards_satellite_style)

    clicked_map_style = {
        'width': '100%', 'min-width': '100%', 'max-width': '100%', 'height': '45vh',
        'padding': '0.5rem', 'background-color': '#1a1a1a', 'border': '2px solid #444',
        'border-radius': '8px', 'margin': '0.2rem 0', 'position': 'relative',
        'transition': 'width 0.3s ease, height 0.3s ease'
    }
    visible_table_style = {
        'display': 'block', 'width': '30%', 'height': '52vh',
        'padding': '0.5rem', 'margin': '0.2rem', 'overflow-y': 'auto',
        'background-color': '#1a1a1a', 'border': '2px solid #444', 'border-radius': '8px'
    }
    visible_plot_style = {
        'height': '50vh', 'display': 'block', 'padding': '0.5rem', 'background-color': '#1a1a1a',
        'border': '2px solid #444', 'border-radius': '8px', 'margin': '0.2rem 0',
        'overflow-y': 'auto', 'width': '100%'
    }
    visible_satellite_style = {
        'display': 'block', 'width': '70%', 'height': '52vh', 'overflow': 'auto',
        'box-sizing': 'border-box', 'background-color': '#1a1a1a', 'border': '2px solid #444',
        'border-radius': '8px', 'margin': '0.2rem'
    }
    visible_weather_style = {
        'display': 'block', 'width': '100%', 'height': '98vh',
        'overflow': 'auto', 'box-sizing': 'border-box',
        'background-color': '#1a1a1a', 'border': '2px solid #444', 'border-radius': '8px',
        'margin': '0.2rem 0'
    }
    visible_digital_twin_style = {
        'height': '50vh', 'display': 'block',
        'padding': '0.5rem', 'background-color': '#1a1a1a',
        'border': '2px solid #444', 'border-radius': '8px', 'margin': '0.2rem 0', 'width': '100%'
    }
    visible_side_by_side_style = {
        'display': 'flex', 'flex-direction': 'row', 'width': '50vw', 'min-width': '50vw',
        'max-width': '50vw', 'margin': '0', 'padding': '0', 'gap': '0.2rem'
    }
    visible_map_table_style = {
        'display': 'flex', 'flex-direction': 'column', 'width': '50vw', 'min-width': '50vw',
        'max-width': '50vw', 'margin': '0', 'padding': '0'
    }
    visible_cards_satellite_style = {
        'display': 'flex', 'flex-direction': 'row', 'width': '100%',
        'gap': '0.2rem'
    }

    point_index = click_info['index']
    selected_row = df.iloc[point_index]
    installation_date = selected_row['StructureInstallationDate']
    ams_ref = selected_row['AMSAssetRef']
    lat = selected_row['Latitude']
    lon = selected_row['Longitude']
    
    # Generate card tiles
    card_data = [
        ('AMS Asset Ref', selected_row['AMSAssetRef']),
        ('Site Name', selected_row['SiteName']),
        ('Structure Class', selected_row['StructureClassCode']),
        ('Height', f"{selected_row['Height']} m")
    ]

    cards = html.Div(
        children=[
            html.Div(
                children=[
                    html.H3(title, style={'font-weight': '700', 'color': '#ffffff', 'margin': '0.5rem 0', 'font-family': '"Orbitron", sans-serif'}),
                    html.P(value, style={'margin': '0.25rem 0', 'font-size': '0.875rem'})
                ],
                className='card'
            ) for title, value in card_data
        ],
        className='card-container',
        style={'width': '100%'}
    )
    
    # Generate maintenance plot
    structure_df = maintenance_df[maintenance_df['AMSAssetRef'] == ams_ref].copy()
    structure_df["Y_Value"] = structure_df["RiskRating_Cleaned"].map(lambda x: severity_levels.get(x, (-1, "black"))[0])
    structure_df["Color"] = structure_df["RiskRating_Cleaned"].map(lambda x: severity_levels.get(x, (-1, "black"))[1])
    structure_df = structure_df.dropna(subset=['IssueCreated', 'Y_Value'])
    
    y_ticks_labels = {v[0]: k for k, v in severity_levels.items()}
    
    fig = px.scatter(
        structure_df,
        x="IssueCreated",
        y="Y_Value",
        hover_data={"IssueDescription": True, "IssueCreated": True, "Y_Value": False},
        labels={"IssueCreated": "Time (Issue Created)", "Y_Value": "Severity Level"},
        title=f"Maintenance Issues for {ams_ref}"
    )
    
    fig.update_traces(
        marker=dict(
            color=structure_df['Color'],
            size=12,
            opacity=0.9,
            line=dict(width=1, color="black")
        )
    )
    
    fig.update_layout(
        yaxis=dict(
            tickmode="array",
            tickvals=list(y_ticks_labels.keys()),
            ticktext=list(y_ticks_labels.values()),
            title_font=dict(color="white"),
            tickfont=dict(color="white"),
            showgrid=True,
            gridcolor="rgba(255,255,255,0.2)"
        ),
        xaxis=dict(
            tickformat="%Y-%m-%d",
            title_font=dict(color="white"),
            tickfont=dict(color="white"),
            showgrid=True,
            gridcolor="rgba(255,255,255,0.2)"
        ),
        template="plotly_dark",
        plot_bgcolor="#1a1a1a",
        paper_bgcolor="#1a1a1a",
        font=dict(color="white"),
        height=600,
        showlegend=False
    )
    
    plot_content = [
        html.H2("Maintenance Issues", style={'font-family': 'Roboto, sans-serif'}),
        dcc.Graph(figure=fig)
    ]
    
    satellite_fig = create_satellite_figure(lat, lon, selected_row['Height'])
    
    return (clicked_map_style,
            visible_table_style,
            cards,
            visible_plot_style,
            plot_content,
            visible_satellite_style,
            visible_weather_style,
            satellite_fig,
            visible_digital_twin_style,
            visible_side_by_side_style,
            visible_map_table_style,
            visible_cards_satellite_style)

# Callback to update weather plots with loading
@app.callback(
    Output('weather-plots', 'children'),
    [Input('pydeck-map', 'clickInfo')]
)
def update_weather_plots(click_info):
    if not click_info or 'object' not in click_info:
        return html.Div("No weather data available", style={'color': 'white'})
    
    point_index = click_info['index']
    selected_row = df.iloc[point_index]
    installation_date = selected_row['StructureInstallationDate']
    lat = selected_row['Latitude']
    lon = selected_row['Longitude']
    ams_ref = selected_row['AMSAssetRef']
    
    weather_df = fetch_weather_data(lat, lon, installation_date)
    weather_df = weather_df.set_index('date').resample('ME').mean().reset_index()
    weather_plots = create_weather_plots(weather_df, lat, lon, ams_ref)
    
    return weather_plots

if __name__ == '__main__':
    app.run(host="0.0.0.0", port = 8050, debug=True)