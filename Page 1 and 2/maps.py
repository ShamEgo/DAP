import os
import pydeck as pdk
import pandas as pd
import dash
from dash import dcc, html, Dash
from dash.dependencies import Input, Output, State
import dash_deck
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import numpy as np
import openmeteo_requests
import requests_cache
from retry_requests import retry
import json
import uuid

# Visual Crossing API key
WEATHER_API_KEY = "KKLV3UDGTSXTVDNYA7N7QMQFG"

# Load structure details data
df = pd.read_excel('Structure Details_17March2025.xlsx', sheet_name='Amplitel Structure Details')
df = df.drop(df[df['StructureAssetStatus'] == 'REMOVED'].index)
df = df.drop(df[df['StructureAssetStatus'] == 'PROPOSED CREATE'].index)
df = df.fillna(0)

# Load maintenance issues data
maintenance_df = pd.read_excel("Structure Maintenance Issues_17March2025.xlsx", sheet_name="Maintenance Issues")
maintenance_df['RiskRating_Cleaned'] = maintenance_df['RiskRating'].str.extract(r'-\s*(\w+)')
maintenance_df['IssueCreated'] = pd.to_datetime(maintenance_df['IssueCreated'], errors='coerce')

# Define columns to keep
selected_columns = [
    'SiteRef', 'AMSAssetRef', 'address_id_tower', 'State', 'SiteName', 
    'StructureClassCode', 'Height', 'FoundationType', 'HeightExtension', 'WarningLights', 
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

df = df.reset_index(drop=True)
df = df[selected_columns]

# Map corrosion region types to numeric values
mapping = {
    'A (Very Low)': 1, 'B (Low)': 2, 'C (Medium)': 3, 'D (High)': 4,
    'E (Very High)': 5, 'F (Inland Tropical)': 6, float('nan'): float('nan')
}
df['corrosion_region_id'] = df['CorrosionRegionType'].map(mapping).astype('Int64')

# Replace NaN values
df = df.dropna(subset=['Longitude', 'Latitude'])
df['Height'] = df['Height'].fillna(0)
df['corrosion_region_id'] = df['corrosion_region_id'].fillna(0)

# Map WindRegionType and SnowIceRegion
wind_mapping = {'A': 1, 'B': 2, 'C': 3, 'D': 4}
df['wind_region_id'] = df['WindRegionType'].map(wind_mapping).fillna(0).astype('Int64')
snow_mapping = {'No': 0, 'Yes': 1}
df['snow_ice_id'] = df['SnowIceRegion'].map(snow_mapping).fillna(0).astype('Int64')

# Preprocess data for new map
df['Combination'] = df['CorrosionRegionType'].astype(str) + ' | ' + df['StructureClassCode'].astype(str)

# Define color palette for new map
colors = [
    [255, 77, 64], [115, 77, 230], [153, 230, 64], [255, 20, 147], [0, 191, 255],
    [230, 64, 64], [230, 64, 204], [0, 230, 179], [255, 64, 38], [64, 230, 204],
    [255, 204, 64], [64, 77, 230], [238, 130, 238], [230, 64, 77], [255, 165, 0]
]
unique_combinations = df['Combination'].unique()
color_map = {combo: colors[i % len(colors)] for i, combo in enumerate(unique_combinations)}
df['CombinationColor'] = df['Combination'].map(color_map)

# Mapbox token
MAPBOX_TOKEN = "pk.eyJ1IjoiYW51YmhhdmpldGxleSIsImEiOiJjbWFraTFzOXAxYmhzMmpvazU3OXZqZmt4In0.YstTAT4yDGFTU1o0Y3uprg"

# Define severity levels for maintenance plot
severity_levels = {
    "EM": (14, "red"), "EM1": (13, "red"), "EM2": (12, "red"), "EM3": (11, "red"),  
    "UM": (10, "orange"), "PM1": (9, "yellow"), "PM2": (8, "green"), 
    "PM3": (7, "green"), "PM4": (6, "green"), "NSV": (5, "blue"), 
    "TFP": (4, "blue"), "MON": (3, "blue"), "FXD": (2, "gray"), 
    "NID": (1, "gray"), "LCR": (0, "gray")     
}

# Define corrosion data (static, as provided)
components = [
    {"description": "Diagonal Raker", "part_no": "4.1", "metal_loss": 80},
    {"description": "Horizontal Brace", "part_no": "4.3", "metal_loss": 80},
    {"description": "Horizontal Brace", "part_no": "6.11", "metal_loss": 30},
    {"description": "Waveguide Gantry Joiner", "part_no": "5.6", "metal_loss": 80},
    {"description": "Ladder Rung", "part_no": "5.2", "metal_loss": 40},
    {"description": "Ladder Barrel Hoop", "part_no": "4.15", "metal_loss": 80},
    {"description": "Leg Splice Plate", "part_no": "6.13", "metal_loss": 80},
    {"description": "Internal Diagonal Brace", "part_no": "8A", "metal_loss": 80},
    {"description": "Platform Mesh Support", "part_no": "5.7", "metal_loss": 80},
    {"description": "Diagonal Raker", "part_no": "93", "metal_loss": 30},
    {"description": "Horizontal Brace", "part_no": "108", "metal_loss": 30},
    {"description": "Stub Leg", "part_no": "NA", "metal_loss": 10},
]

# Function to create Pydeck layer for existing map
def create_layer(category):
    color_expression = {
        'corrosion_region_id': [
            "corrosion_region_id === 1 ? 255 : corrosion_region_id === 2 ? 255 : corrosion_region_id === 3 ? 255 : corrosion_region_id === 4 ? 0 : corrosion_region_id === 5 ? 255 : corrosion_region_id === 6 ? 0 : 50",
            "corrosion_region_id === 1 ? 255 : corrosion_region_id === 2 ? 255 : corrosion_region_id === 3 ? 0 : corrosion_region_id === 4 ? 255 : corrosion_region_id === 5 ? 0 : corrosion_region_id === 6 ? 173 : 50",
            "corrosion_region_id === 1 ? 255 : corrosion_region_id === 2 ? 0 : corrosion_region_id === 3 ? 255 : corrosion_region_id === 4 ? 0 : corrosion_region_id === 5 ? 0 : corrosion_region_id === 6 ? 255 : 50",
            255
        ],
        'wind_region_id': [
            "wind_region_id === 1 ? 0 : wind_region_id === 2 ? 0 : wind_region_id === 3 ? 0 : wind_region_id === 4 ? 255 : 100",
            "wind_region_id === 1 ? 255 : wind_region_id === 2 ? 165 : wind_region_id === 3 ? 0 : wind_region_id === 4 ? 0 : 100",
            "wind_region_id === 1 ? 0 : wind_region_id === 2 ? 255 : wind_region_id === 3 ? 255 : wind_region_id === 4 ? 0 : 100",
            140
        ],
        'snow_ice_id': [
            "snow_ice_id === 0 ? 0 : snow_ice_id === 1 ? 255 : 100",
            "snow_ice_id === 0 ? 255 : snow_ice_id === 1 ? 255 : 100",
            "snow_ice_id === 0 ? 0 : snow_ice_id === 1 ? 255 : 100",
            140
        ],
        'PaintingType': [
            "PaintingType === 'AVIATION' ? 173 : PaintingType === 'ENVIRONMENT / AESTHETIC' ? 0 : PaintingType === 'NOT PAINTED' ? 138 : PaintingType === 'PROTECTION' ? 32 : 100",
            "PaintingType === 'AVIATION' ? 216 : PaintingType === 'ENVIRONMENT / AESTHETIC' ? 255 : PaintingType === 'NOT PAINTED' ? 1 : PaintingType === 'PROTECTION' ? 53 : 100",
            "PaintingType === 'AVIATION' ? 230 : PaintingType === 'ENVIRONMENT / AESTHETIC' ? 0 : PaintingType === 'NOT PAINTED' ? 1 : PaintingType === 'PROTECTION' ? 212 : 100",
            140
        ]
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

# Initial layer and deck for existing map
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

# Define legend data for existing map
legend_data = {
    'corrosion_region_id': [
        {'label': 'A (Very Low)', 'color': 'rgb(255, 255, 255)'},
        {'label': 'B (Low)', 'color': 'rgb(255, 255, 0)'},
        {'label': 'C (Medium)', 'color': 'rgb(255, 0, 255)'},
        {'label': 'D (High)', 'color': 'rgb(0, 255, 0)'},
        {'label': 'E (Very High)', 'color': 'rgb(255, 0, 0)'},
        {'label': 'F (Inland Tropical)', 'color': 'rgb(0,173,255)'},
    ],
    'wind_region_id': [
        {'label': 'A', 'color': 'rgb(0, 255, 0)'},
        {'label': 'B', 'color': 'rgb(0, 165, 255)'},
        {'label': 'C', 'color': 'rgb(0, 0, 255)'},
        {'label': 'D', 'color': 'rgb(255, 0, 0)'},
    ],
    'snow_ice_id': [
        {'label': 'No', 'color': 'rgb(0, 255, 0)'},
        {'label': 'Yes', 'color': 'rgb(255, 255, 255)'},
    ],
    'PaintingType': [
        {'label': 'Aviation', 'color': 'rgb(173, 216, 230)'},
        {'label': 'Environment/Aesthetic', 'color': 'rgb(0, 255, 0)'},
        {'label': 'Not Painted', 'color': 'rgb(138, 1, 1)'},
        {'label': 'Protection', 'color': 'rgb(32, 53, 212)'},
    ]
}

# Functions for new map
def create_layer_new_map(data):
    return pdk.Layer(
        'ColumnLayer',
        data,
        pickable=True,
        get_position=['Longitude', 'Latitude'],
        get_elevation='Height',
        elevation_scale=100,
        radius=1000,
        get_fill_color='CombinationColor',
        auto_highlight=True
    )

def create_legend_html(active_combinations, color_map):
    legend_html = """
    <div style="position: absolute; top: 10px; left: 10px; background-color: rgba(0, 0, 0, 0.7); padding: 10px; border-radius: 5px; color: white; font-family: 'Roboto', sans-serif; z-index: 1;">
        <h3 style="margin: 0 0 10px 0;">Legend</h3>
        <ul style="list-style-type: none; padding: 0; margin: 0;">
    """
    for combo in active_combinations:
        color = color_map[combo]
        legend_html += f"""
            <li style="margin-bottom: 5px;">
                <span style="display: inline-block; width: 15px; height: 15px; background-color: rgba({color[0]}, {color[1]}, {color[2]}, 1); margin-right: 10px; border-radius: 3px;"></span>
                {combo}
            </li>
        """
    legend_html += """
        </ul>
    </div>
    """
    return legend_html

# Dropdown options for new map
corrosion_options = [{'label': str(val), 'value': str(val)} for val in df['CorrosionRegionType'].unique()]
structure_options = [{'label': str(val), 'value': str(val)} for val in df['StructureClassCode'].unique()]

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
            body {
                margin: 0;
                padding: 0;
                background-color: black;
            }
            .tabs-container {
                width: 98%;
                margin: 0 auto;
            }
            .tabs-container .dash-tabs {
                background-color: #808080;
                border: 2px solid #00BFFF;
                border-radius: 5px;
                padding: 5px;
            }
            .tabs-container .dash-tabs li {
                display: inline-block;
            }
            .tabs-container .dash-tabs li a {
                color: #ffffff;
                font-family: 'Roboto', sans-serif;
                padding: 10px 20px;
                border: 2px solid #00BFFF;
                border-bottom: none;
                border-radius: 5px 5px 0 0;
                background-color: #808080;
                margin-right: 5px;
                text-decoration: none;
                transition: background-color 0.2s ease;
            }
            .tabs-container .dash-tabs li a:hover {
                background-color: #666666;
            }
            .tabs-container .dash-tabs li.dash-tab--selected a {
                background-color: #00BFFF;
                color: #ffffff;
                border: 2px solid #00BFFF;
                border-bottom: none;
                font-weight: bold;
            }
            .custom-radio-input {
                -webkit-appearance: none;
                -moz-appearance: none;
                appearance: none;
                width: 18px;
                height: 18px;
                border: 2px solid #4169E1;
                border-radius: 50%;
                background-color: #333333;
                cursor: pointer;
                vertical-align: middle;
                margin-right: 8px;
                transition: all 0.2s ease;
                position: relative;
            }
            .custom-radio-input:checked::before {
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 10px;
                height: 10px;
                background-color: #4169E1;
                border-radius: 50%;
            }
            .custom-radio-input:focus {
                outline: none;
                box-shadow: 0 0 0 2px rgba(65, 105, 225, 0.5);
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

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    distance = R * c
    return distance

# Mapping of state abbreviations to GNAF file names
state_gnaf_mapping = {
    'NSW': 'GNAF_CORE_NSW.csv',
    'VIC': 'GNAF_CORE_VIC.csv',
    'QLD': 'GNAF_CORE_QLD.csv',
    'SA': 'GNAF_CORE_SA.csv',
    'WA': 'GNAF_CORE_WA.csv',
    'TAS': 'GNAF_CORE_TAS.csv',
    'NT': 'GNAF_CORE_NT.csv',
    'ACT': 'GNAF_CORE_ACT.csv'
}

def load_gnaf_dataframe(state):
    if state in state_gnaf_mapping:
        file_path = state_gnaf_mapping[state]
        try:
            return pd.read_csv(file_path, usecols=['ADDRESS_LABEL', 'FLAT_TYPE', 'LATITUDE', 'LONGITUDE'])
        except FileNotFoundError:
            print(f"File {file_path} not found.")
            return pd.DataFrame()
    return pd.DataFrame()

def create_satellite_figure(lat, lon, height, zoom=17):
    satellite_token = 'pk.eyJ1IjoiYW51YmhhdmpldGxleSIsImEiOiJjbWFraTE3c2kwOXl6MmtxNGJlanpkbGFtIn0.hkV6YZvZvqCGIFkHaPtkug'
    tower_data = pd.DataFrame({
        'latitude': [lat],
        'longitude': [lon],
    })
    radius_in_km = height / 1000
    radius_in_degrees = radius_in_km / 111
    num_points = 50
    circle_lat = [lat + radius_in_degrees * np.cos(2 * np.pi * i / num_points)
                  for i in range(num_points + 1)]
    circle_lon = [lon + radius_in_degrees * np.sin(2 * np.pi * i / num_points) / np.cos(lat * np.pi / 180)
                  for i in range(num_points + 1)]
    circle_data = pd.DataFrame({
        'latitude': circle_lat,
        'longitude': circle_lon,
        'name': [f'Radius ({height}m)'] * (num_points + 1)
    })
    fig = px.scatter_mapbox(
        tower_data,
        lat='latitude',
        lon='longitude',
        color_discrete_sequence=['red'],
        size=[14],
        mapbox_style='mapbox://styles/anubhavjetley/ckvg4uofg00vc15pi7q90kpkd',
        zoom=zoom,
        center={'lat': lat, 'lon': lon},
    )
    fig.add_traces(
        px.scatter_mapbox(
            circle_data,
            lat='latitude',
            lon='longitude',
            color_discrete_sequence=['yellow'],
            hover_name='name'
        ).update_traces(mode='lines', line=dict(width=2)).data
    )
    fig.update_layout(
        mapbox=dict(
            accesstoken='pk.eyJ1IjoiYW51YmhhdmpldGxleSIsImEiOiJjbWFraHpzbmkwOHRlMmtvaDhhaDY1ajM0In0.MolCp0Po3LjGf8z5ebKJig',
            style='mapbox://styles/anubhavjetley/ckvg4uofg00vc15pi7q90kpkd',
            center=dict(lat=lat, lon=lon),
            zoom=zoom
        ),
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0},
        showlegend=True,
        legend=dict(x=0.01, y=0.99, bgcolor='rgba(0,0,0,0.5)', font=dict(color='white')),
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a'
    )
    return fig

GOOGLE_MAPS_API_KEY = "AIzaSyCyvuTRDR6I-BoYREo0kf_ZrzYcbOaI_SU"

tab_style = {
    'backgroundColor': '#1a1a1a',
    'color': 'white',
    'borderBottom': '1px solid #d6d6d6',
    'padding': '6px',
    'fontWeight': 'bold'
}

tab_selected_style = {
    'borderTop': '1px solid #d6d6d6',
    'borderBottom': '1px solid #d6d6d6',
    'backgroundColor': 'black',
    'color': 'white',
    'padding': '6px'
}

def create_street_view_html(lat, lon):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Satellite View</title>
        <script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}"></script>
        <script>
            function initSatelliteView() {{
                var location = {{lat: {lat}, lng: {lon}}};
                var map = new google.maps.Map(
                    document.getElementById('satellite-view'),
                    {{
                        center: location,
                        zoom: 19,
                        mapTypeId: 'satellite'
                    }}
                );
                var marker = new google.maps.Marker({{
                    position: location,
                    map: map
                }});
            }}
        </script>
        <style>
            #satellite-view {{
                height: 100%;
                width: 100%;
            }}
            html, body {{
                height: 100%;
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body onload="initSatelliteView()">
        <div id='satellite-view'></div>
    </body>
    </html>
    """

# Setup Open-Meteo API client
cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

def fetch_air_quality_data(lat, lon):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["sulphur_dioxide", "pm10", "pm2_5"],
        "start_date": "2013-01-01",
        "end_date": "2025-05-10"
    }
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    hourly = response.Hourly()
    hourly_sulphur_dioxide = hourly.Variables(0).ValuesAsNumpy()
    hourly_pm10 = hourly.Variables(1).ValuesAsNumpy()
    hourly_pm2_5 = hourly.Variables(2).ValuesAsNumpy()
    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        ),
        "sulphur_dioxide": hourly_sulphur_dioxide,
        "pm10": hourly_pm10,
        "pm2_5": hourly_pm2_5
    }
    air_quality_df = pd.DataFrame(data=hourly_data)
    air_quality_df['date'] = pd.to_datetime(air_quality_df['date'])
    air_quality_daily = air_quality_df.resample('D', on='date').mean().reset_index()
    return air_quality_daily

def fetch_weather_data(lat, lon):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2013-01-01",
        "end_date": "2025-05-10",
        "daily": [
            "relative_humidity_2m_mean", "relative_humidity_2m_max", "relative_humidity_2m_min",
            "soil_moisture_0_to_100cm_mean",
            "wind_speed_10m_mean", "wind_speed_10m_max", "wind_speed_10m_min",
            "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
            "surface_pressure_mean", "surface_pressure_max", "surface_pressure_min"
        ],
        "timezone": "Australia/Sydney"
    }
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    daily = response.Daily()
    daily_data = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        ),
        "relative_humidity_2m_mean": daily.Variables(0).ValuesAsNumpy(),
        "relative_humidity_2m_max": daily.Variables(1).ValuesAsNumpy(),
        "relative_humidity_2m_min": daily.Variables(2).ValuesAsNumpy(),
        "soil_moisture_0_to_100cm_mean": daily.Variables(3).ValuesAsNumpy(),
        "wind_speed_10m_mean": daily.Variables(4).ValuesAsNumpy(),
        "wind_speed_10m_max": daily.Variables(5).ValuesAsNumpy(),
        "wind_speed_10m_min": daily.Variables(6).ValuesAsNumpy(),
        "temperature_2m_mean": daily.Variables(7).ValuesAsNumpy(),
        "temperature_2m_max": daily.Variables(8).ValuesAsNumpy(),
        "temperature_2m_min": daily.Variables(9).ValuesAsNumpy(),
        "surface_pressure_mean": daily.Variables(10).ValuesAsNumpy(),
        "surface_pressure_max": daily.Variables(11).ValuesAsNumpy(),
        "surface_pressure_min": daily.Variables(12).ValuesAsNumpy()
    }
    weather_df = pd.DataFrame(data=daily_data)
    return weather_df

def create_weather_plots(weather_df, air_quality_df):
    if (weather_df is None or weather_df.empty) and (air_quality_df is None or air_quality_df.empty):
        return html.Div("No weather or air quality data available", style={'color': 'white'})

    weather_rows = []
    if weather_df is not None and not weather_df.empty:
        weather_df['date'] = pd.to_datetime(weather_df['date'])
        # Resample to monthly aggregates
        weather_monthly = weather_df.set_index('date').resample('M').agg({
            'relative_humidity_2m_mean': 'mean',
            'relative_humidity_2m_max': ['mean', 'min', 'max'],
            'relative_humidity_2m_min': 'mean',
            'soil_moisture_0_to_100cm_mean': 'mean',
            'wind_speed_10m_mean': 'mean',
            'wind_speed_10m_max': ['mean', 'min', 'max'],
            'wind_speed_10m_min': 'mean',
            'temperature_2m_mean': 'mean',
            'temperature_2m_max': ['mean', 'min', 'max'],
            'temperature_2m_min': 'mean',
            'surface_pressure_mean': 'mean',
            'surface_pressure_max': ['mean', 'min', 'max'],
            'surface_pressure_min': 'mean'
        }).reset_index()

        # Flatten multi-level column names
        weather_monthly.columns = [
            'date',
            'relative_humidity_2m_mean',
            'relative_humidity_2m_max_mean', 'relative_humidity_2m_max_min', 'relative_humidity_2m_max_max',
            'relative_humidity_2m_min_mean',
            'soil_moisture_0_to_100cm_mean',
            'wind_speed_10m_mean',
            'wind_speed_10m_max_mean', 'wind_speed_10m_max_min', 'wind_speed_10m_max_max',
            'wind_speed_10m_min_mean',
            'temperature_2m_mean',
            'temperature_2m_max_mean', 'temperature_2m_max_min', 'temperature_2m_max_max',
            'temperature_2m_min_mean',
            'surface_pressure_mean',
            'surface_pressure_max_mean', 'surface_pressure_max_min', 'surface_pressure_max_max',
            'surface_pressure_min_mean'
        ]

        # Calculate overall mean values for weather variables
        mean_values = {
            'relative_humidity_2m_mean': weather_df['relative_humidity_2m_mean'].mean(),
            'soil_moisture_0_to_100cm_mean': weather_df['soil_moisture_0_to_100cm_mean'].mean(),
            'wind_speed_10m_mean': weather_df['wind_speed_10m_mean'].mean(),
            'temperature_2m_mean': weather_df['temperature_2m_mean'].mean(),
            'surface_pressure_mean': weather_df['surface_pressure_mean'].mean(),
            'relative_humidity_2m': (
                weather_df['relative_humidity_2m_min'].mean() +
                weather_df['relative_humidity_2m_mean'].mean() +
                weather_df['relative_humidity_2m_max'].mean()
            ) / 3,
            'wind_speed_10m': (
                weather_df['wind_speed_10m_min'].mean() +
                weather_df['wind_speed_10m_mean'].mean() +
                weather_df['wind_speed_10m_max'].mean()
            ) / 3,
            'temperature_2m': (
                weather_df['temperature_2m_min'].mean() +
                weather_df['temperature_2m_mean'].mean() +
                weather_df['temperature_2m_max'].mean()
            ) / 3,
            'surface_pressure': (
                weather_df['surface_pressure_min'].mean() +
                weather_df['surface_pressure_mean'].mean() +
                weather_df['surface_pressure_max'].mean()
            ) / 3
        }

        # Create card component
        def create_card(title, value, unit):
            return html.Div(
                [
                    html.H4(title, style={'margin': '0', 'fontSize': '14px', 'color': '#e0e0e0'}),
                    html.H2(f"{value:.2f} {unit}", style={'margin': '5px 0 0 0', 'fontSize': '24px', 'color': '#4169E1'})
                ],
                style={
                    'backgroundColor': '#1a1a1a',
                    'border': '2px solid #444',
                    'borderRadius': '8px',
                    'padding': '10px',
                    'textAlign': 'center',
                    'marginBottom': '10px',
                    'width': '100%',
                    'boxShadow': '0 2px 4px rgba(0,0,0,0.2)'
                }
            )

        # Create figures for mean values
        rh_mean_fig = px.line(
            weather_monthly, x='date', y='relative_humidity_2m_mean',
            title='Monthly Mean Relative Humidity at 2m (%)',
            labels={'relative_humidity_2m_mean': 'Relative Humidity (%)', 'date': 'Date'}
        )
        soil_moisture_fig = px.line(
            weather_monthly, x='date', y='soil_moisture_0_to_100cm_mean',
            title='Monthly Mean Soil Moisture 0-100cm (m³/m³)',
            labels={'soil_moisture_0_to_100cm_mean': 'Soil Moisture (m³/m³)', 'date': 'Date'}
        )
        wind_speed_mean_fig = px.line(
            weather_monthly, x='date', y='wind_speed_10m_mean',
            title='Monthly Mean Wind Speed at 10m (km/h)',
            labels={'wind_speed_10m_mean': 'Wind Speed (km/h)', 'date': 'Date'}
        )
        temp_mean_fig = px.line(
            weather_monthly, x='date', y='temperature_2m_mean',
            title='Monthly Mean Temperature at 2m (°C)',
            labels={'temperature_2m_mean': 'Temperature (°C)', 'date': 'Date'}
        )
        pressure_mean_fig = px.line(
            weather_monthly, x='date', y='surface_pressure_mean',
            title='Monthly Mean Surface Pressure (hPa)',
            labels={'surface_pressure_mean': 'Surface Pressure (hPa)', 'date': 'Date'}
        )

        # Create figure for relative humidity with mean, min, max
        rh_fig = go.Figure()
        rh_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['relative_humidity_2m_max_mean'],
            mode='lines', name='Mean Relative Humidity', line=dict(color='#4169E1')
        ))
        rh_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['relative_humidity_2m_max_max'],
            mode='lines', name='Max Relative Humidity', line=dict(color='#FF4500', dash='dash')
        ))
        rh_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['relative_humidity_2m_max_min'],
            mode='lines', name='Min Relative Humidity', line=dict(color='#32CD32', dash='dash')
        ))
        rh_fig.update_layout(
            title='Monthly Relative Humidity at 2m (Mean, Min, Max) (%)',
            xaxis_title='Date',
            yaxis_title='Relative Humidity (%)',
            template="plotly_dark",
            plot_bgcolor="#1a1a1a",
            paper_bgcolor="#1a1a1a",
            font=dict(color="white"),
            height=300,
            margin=dict(l=40, r=40, t=40, b=20)
        )

        # Create figure for wind speed with mean, min, max
        wind_fig = go.Figure()
        wind_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['wind_speed_10m_max_mean'],
            mode='lines', name='Mean Wind Speed', line=dict(color='#4169E1')
        ))
        wind_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['wind_speed_10m_max_max'],
            mode='lines', name='Max Wind Speed', line=dict(color='#FF4500', dash='dash')
        ))
        wind_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['wind_speed_10m_max_min'],
            mode='lines', name='Min Wind Speed', line=dict(color='#32CD32', dash='dash')
        ))
        wind_fig.update_layout(
            title='Monthly Wind Speed at 10m (Mean, Min, Max) (km/h)',
            xaxis_title='Date',
            yaxis_title='Wind Speed (km/h)',
            template="plotly_dark",
            plot_bgcolor="#1a1a1a",
            paper_bgcolor="#1a1a1a",
            font=dict(color="white"),
            height=300,
            margin=dict(l=40, r=40, t=40, b=20)
        )

        # Create figure for temperature with mean, min, max
        temp_fig = go.Figure()
        temp_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['temperature_2m_max_mean'],
            mode='lines', name='Mean Temperature', line=dict(color='#4169E1')
        ))
        temp_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['temperature_2m_max_max'],
            mode='lines', name='Max Temperature', line=dict(color='#FF4500', dash='dash')
        ))
        temp_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['temperature_2m_max_min'],
            mode='lines', name='Min Temperature', line=dict(color='#32CD32', dash='dash')
        ))
        temp_fig.update_layout(
            title='Monthly Temperature at 2m (Mean, Min, Max) (°C)',
            xaxis_title='Date',
            yaxis_title='Temperature (°C)',
            template="plotly_dark",
            plot_bgcolor="#1a1a1a",
            paper_bgcolor="#1a1a1a",
            font=dict(color="white"),
            height=300,
            margin=dict(l=40, r=40, t=40, b=20)
        )

        # Create figure for surface pressure with mean, min, max
        pressure_fig = go.Figure()
        pressure_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['surface_pressure_max_mean'],
            mode='lines', name='Mean Surface Pressure', line=dict(color='#4169E1')
        ))
        pressure_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['surface_pressure_max_max'],
            mode='lines', name='Max Surface Pressure', line=dict(color='#FF4500', dash='dash')
        ))
        pressure_fig.add_trace(go.Scatter(
            x=weather_monthly['date'], y=weather_monthly['surface_pressure_max_min'],
            mode='lines', name='Min Surface Pressure', line=dict(color='#32CD32', dash='dash')
        ))
        pressure_fig.update_layout(
            title='Monthly Surface Pressure (Mean, Min, Max) (hPa)',
            xaxis_title='Date',
            yaxis_title='Surface Pressure (hPa)',
            template="plotly_dark",
            plot_bgcolor="#1a1a1a",
            paper_bgcolor="#1a1a1a",
            font=dict(color="white"),
            height=300,
            margin=dict(l=40, r=40, t=40, b=20)
        )

        # Apply consistent styling to all Plotly Express figures
        for fig in [rh_mean_fig, soil_moisture_fig, wind_speed_mean_fig, temp_mean_fig, pressure_mean_fig]:
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor="#1a1a1a",
                paper_bgcolor="#1a1a1a",
                font=dict(color="white"),
                height=300,
                margin=dict(l=40, r=40, t=40, b=20)
            )
            fig.update_traces(line_color='#4169E1')

        # Organize weather plots with cards into rows
        weather_plot_pairs = [
            (
                [
                    create_card("Overall Mean Relative Humidity", mean_values['relative_humidity_2m_mean'], "%"),
                    dcc.Graph(figure=rh_mean_fig)
                ],
                [
                    create_card("Overall Mean Soil Moisture", mean_values['soil_moisture_0_to_100cm_mean'], "m³/m³"),
                    dcc.Graph(figure=soil_moisture_fig)
                ]
            ),
            (
                [
                    create_card("Overall Mean Wind Speed", mean_values['wind_speed_10m_mean'], "km/h"),
                    dcc.Graph(figure=wind_speed_mean_fig)
                ],
                [
                    create_card("Overall Mean Temperature", mean_values['temperature_2m_mean'], "°C"),
                    dcc.Graph(figure=temp_mean_fig)
                ]
            ),
            (
                [
                    create_card("Overall Mean Surface Pressure", mean_values['surface_pressure_mean'], "hPa"),
                    dcc.Graph(figure=pressure_mean_fig)
                ],
                [
                    create_card("Overall Average Relative Humidity", mean_values['relative_humidity_2m'], "%"),
                    dcc.Graph(figure=rh_fig)
                ]
            ),
            (
                [
                    create_card("Overall Average Wind Speed", mean_values['wind_speed_10m'], "km/h"),
                    dcc.Graph(figure=wind_fig)
                ],
                [
                    create_card("Overall Average Temperature", mean_values['temperature_2m'], "°C"),
                    dcc.Graph(figure=temp_fig)
                ]
            ),
            (
                [
                    create_card("Overall Average Surface Pressure", mean_values['surface_pressure'], "hPa"),
                    dcc.Graph(figure=pressure_fig)
                ],
                None
            )
        ]
        weather_rows = [
            html.Div([
                html.Div(pair[0], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top'}),
                html.Div(pair[1] if pair[1] else html.Div(), style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%'})
            ], style={'width': '100%', 'marginBottom': '20px'})
            for pair in weather_plot_pairs
        ]

    air_quality_rows = []
    if air_quality_df is not None and not air_quality_df.empty:
        air_quality_df['date'] = pd.to_datetime(air_quality_df['date'])
        # Resample air quality data to monthly means
        air_quality_monthly = air_quality_df.set_index('date').resample('M').mean().reset_index()
        
        # Calculate overall mean values for air quality variables
        air_quality_means = {
            'sulphur_dioxide': air_quality_df['sulphur_dioxide'].mean(),
            'pm10': air_quality_df['pm10'].mean(),
            'pm2_5': air_quality_df['pm2_5'].mean()
        }

        so2_fig = px.line(
            air_quality_monthly, x='date', y='sulphur_dioxide',
            title='Monthly Mean Sulphur Dioxide (µg/m³)',
            labels={'sulphur_dioxide': 'SO2 (µg/m³)', 'date': 'Date'}
        )
        pm10_fig = px.line(
            air_quality_monthly, x='date', y='pm10',
            title='Monthly Mean PM10 Concentration (µg/m³)',
            labels={'pm10': 'PM10 (µg/m³)', 'date': 'Date'}
        )
        pm2_5_fig = px.line(
            air_quality_monthly, x='date', y='pm2_5',
            title='Monthly Mean PM2.5 Concentration (µg/m³)',
            labels={'pm2_5': 'PM2.5 (µg/m³)', 'date': 'Date'}
        )
        for fig in [so2_fig, pm10_fig, pm2_5_fig]:
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor="#1a1a1a",
                paper_bgcolor="#1a1a1a",
                font=dict(color="white"),
                height=300,
                margin=dict(l=40, r=40, t=40, b=20)
            )
            fig.update_traces(line_color='#4169E1')
        
        air_quality_rows = [
            html.Div([
                html.Div([
                    create_card("Overall Mean Sulphur Dioxide", air_quality_means['sulphur_dioxide'], "µg/m³"),
                    dcc.Graph(figure=so2_fig)
                ], style={'width': '32%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginRight': '1%'}),
                html.Div([
                    create_card("Overall Mean PM10", air_quality_means['pm10'], "µg/m³"),
                    dcc.Graph(figure=pm10_fig)
                ], style={'width': '32%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginRight': '1%'}),
                html.Div([
                    create_card("Overall Mean PM2.5", air_quality_means['pm2_5'], "µg/m³"),
                    dcc.Graph(figure=pm2_5_fig)
                ], style={'width': '32%', 'display': 'inline-block', 'verticalAlign': 'top'})
            ], style={'width': '100%', 'marginBottom': '20px'})
        ]

    return weather_rows + air_quality_rows

# Layout of the app
app.layout = html.Div([
    html.H1(
        "Amplitel UTS TRU Dashboard",
        style={
            'textAlign': 'center', 'color': 'white', 'fontFamily': '"Orbitron", sans-serif',
            'fontWeight': '700', 'padding': '20px', 'margin': '0', 'fontSize': '36px',
            'letterSpacing': '2px'
        }
    ),
    dcc.Tabs(
        id='tabs',
        value='tab-1',
        children=[
            dcc.Tab(
                label='Existing Tower Site Fingerprint',
                value='tab-1',
                style=tab_style,
                selected_style=tab_selected_style,
                children=[
                    html.Div([
                        html.Div([
                            dcc.Dropdown(
                                id='search-bar',
                                options=[{'label': ref, 'value': ref} for ref in df['AMSAssetRef'].unique()],
                                placeholder='Search by AMS Asset Ref...',
                                style={
                                    'width': '300px',
                                    'backgroundColor': '#1a1a1a',
                                    'color': '#000000',
                                    'fontFamily': '"Roboto", sans-serif',
                                    'fontSize': '16px',
                                    'borderRadius': '24px',
                                    'boxShadow': '0 1px 6px rgba(32, 33, 36, 0.28)',
                                    'padding': '8px'
                                },
                                searchable=True,
                                clearable=True,
                                optionHeight=35
                            ),
                        ], style={'display': 'inline-block', 'verticalAlign': 'middle', 'marginRight': '20px'}),
                        dcc.RadioItems(
                            id='category-selector',
                            options=[
                                {'label': 'Corrosion Region Type', 'value': 'corrosion_region_id'},
                                {'label': 'Wind Region Type', 'value': 'wind_region_id'},
                                {'label': 'Snow/Ice Region', 'value': 'snow_ice_id'},
                                {'label': 'Paint Type', 'value': 'PaintingType'}
                            ],
                            value='corrosion_region_id',
                            labelStyle={
                                'display': 'inline-block', 'marginRight': '25px', 'color': '#ffffff',
                                'fontFamily': 'Roboto, sans-serif', 'fontSize': '16px', 'padding': '8px 12px',
                                'cursor': 'pointer'
                            },
                            style={
                                'padding': '15px', 'display': 'inline-block', 'alignItems': 'center'
                            },
                            inputStyle={
                                'marginRight': '8px', 'width': '18px', 'height': '18px', 'cursor': 'pointer',
                                'verticalAlign': 'middle', 'appearance': 'none', 'border': '2px solid #4169E1',
                                'borderRadius': '50%', 'backgroundColor': '#333333', 'transition': 'all 0.2s ease'
                            },
                            inputClassName='custom-radio-input'
                        ),
                    ], style={
                        'border': '2px solid #444444', 'backgroundColor': '#1a1a1a', 'borderRadius': '8px',
                        'marginTop': '-65px', 'margin': '5px auto', 'width': 'fit-content',
                        'boxShadow': '0 2px 10px rgba(0, 0, 0, 0.3)', 'position': 'relative', 'zIndex': '10',
                        'display': 'flex', 'justifyContent': 'flex-start', 'alignItems': 'center', 'padding': '10px'
                    }),
                    html.Div(
                        id='legend-container',
                        style={
                            'position': 'absolute', 'top': '158px', 'left': '0.5px',
                            'backgroundColor': 'rgba(0, 0, 0, 0.7)', 'padding': '10px', 'borderRadius': '5px',
                            'zIndex': '10', 'color': 'white', 'fontFamily': 'Roboto, sans-serif'
                        }
                    ),
                    html.Div([
                        html.Div(
                            id='map-container',
                            children=[
                                dash_deck.DeckGL(
                                    id='pydeck-map',
                                    data=r.to_json(),
                                    tooltip=initial_tooltip,
                                    enableEvents=['click'],
                                    style={
                                        'width': '98%', 'height': '65vh', 'marginLeft': '0.5%', 'marginTop': '15%',
                                    },
                                    mapboxKey=MAPBOX_TOKEN
                                )
                            ],
                            style={
                                'display': 'inline-block', 'width': '100%', 'height': '66vh',
                                'verticalAlign': 'top', 'backgroundColor': 'black',
                            }
                        ),
                        html.Div(
                            id='table-container',
                            children=[
                                html.H2("Tower Site Details", style={
                                    'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif'
                                }),
                                html.Div(
                                    id="data-table",
                                    style={
                                        'overflowY': 'scroll', 'maxHeight': '57vh', 'backgroundColor': 'black',
                                        'border': '2px solid white', 'color': 'white', 'padding': '10px',
                                        'display': 'none'
                                    }
                                )
                            ],
                            style={
                                'marginTop': '0.5%', 'display': 'inline-block', 'width': '43%',
                                'verticalAlign': 'top', 'marginLeft': 'auto', 'border': '2px solid white',
                                'backgroundColor': 'black', 'display': 'none'
                            }
                        ),
                    ], style={
                        'display': 'flex', 'flexDirection': 'row', 'justifyContent': 'space-between',
                        'backgroundColor': 'black', 'width': '100%'
                    }),
                    html.Div([
                        html.Div([
                            html.Div(
                                id='plot-container',
                                style={
                                    'width': '95%', 'margin': '0', 'backgroundColor': '#1a1a1a',
                                    'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px', 'border': '2px solid #444', 'display':'none'
                                }
                            ),
                        ], style={
                            'flex': '1', 'minWidth': '45%', 'marginRight': '0.8%'
                        }),
                        html.Div([
                            dcc.Loading(
                                id="loading-nearby-residences",
                                type="circle",
                                color="#4169E1",
                                children=html.Div(
                                    id='nearby-residences-container',
                                    children=[
                                        html.H2("Residences within 100m", style={
                                            'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif', 'display' : 'none'
                                        }),
                                        html.Div(
                                            id="nearby-residences-table",
                                            style={
                                                'width': '98%', 'overflowY': 'scroll', 'maxHeight': '30vh', 'backgroundColor': '#1a1a1a',
                                                'border': '2px solid white', 'color': 'white', 'padding': '10px', 'margin-bottom': '1.4%', 'display':'none'
                                            }
                                        )
                                    ],
                                    style={
                                        'margin': '0', 'backgroundColor': '#1a1a1a',
                                        'padding': '10px', 'borderRadius': '8px', 'border': '2px solid #444',
                                        'marginBottom': '20px', 'display' : 'none'
                                    }
                                )
                            ),
                            html.Div(
                                id='satellite-container',
                                children=[
                                    html.H2("Mesh Block Zone", style={
                                        'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif'
                                    }),
                                    dcc.Graph(id='satellite-map', style={'height': '400px'})
                                ],
                                style={
                                    'width': '88%', 'margin-left' : '5%', 'backgroundColor': '#1a1a1a',
                                    'padding': '10px', 'borderRadius': '8px', 'marginBottom': '20px','display':'none'
                                }
                            ),
                            html.Div(
                                id='street-view-container',
                                children=[
                                    html.H2("Satellite & Street View", style={
                                        'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif'
                                    }),
                                    html.Iframe(
                                        id='street-view-iframe',
                                        srcDoc=create_street_view_html(-33.47940816, 150.158602),
                                        width="100%",
                                        height="400px",
                                        style={'border': 'none'}
                                    )
                                ],
                                style={
                                    'width': '88%', 'margin-left' : '5%', 'backgroundColor': '#1a1a1a',
                                    'padding': '10px', 'borderRadius': '8px', 'display':'none'
                                }
                            )
                        ], style={
                            'flex': '1', 'minWidth': '45%'
                        })
                    ], style={
                        'display': 'flex', 'flexDirection': 'row', 'width': '98%', 'margin': '0 auto', 'marginTop': '20px', 'gap': '1%'
                    }),
                    html.Div(
                        id='weather-container',
                        children=[
                            html.H2("Historical Weather Data", style={
                                'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif'
                            }),
                            dcc.Loading(
                                id="loading-weather",
                                type="circle",
                                color="#4169E1",
                                children=html.Div(id='weather-plots', style={'display': 'block'})
                            )
                        ],
                        style={
                            'width': '95%', 'margin': '0 auto', 'display': 'none', 'backgroundColor': '#1a1a1a',
                            'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px'
                        }
                    ),
                ]
            ),
            dcc.Tab(
                label='Corrosion Region - Structure Class',
                style=tab_style,
                selected_style=tab_selected_style,
                value='tab-2',
                children=[
                    html.Div(
                        id='new-map-container',
                        children=[
                            html.H2("Corrosion - Structure Class Map", style={
                                'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif'
                            }),
                            html.Div([
                                html.Div([
                                    html.Label('Corrosion Region Type', style={'color': 'white', 'marginBottom': '5px'}),
                                    dcc.Dropdown(
                                        id='corrosion-dropdown',
                                        options=corrosion_options,
                                        multi=True,
                                        value=[corrosion_options[0]['value']],
                                        style={'backgroundColor': '#333', 'color': '#000', 'marginBottom': '10px'}
                                    ),
                                ], style={'width': '300px', 'margin': '10px'}),
                                html.Div([
                                    html.Label('Structure Class Code', style={'color': 'white', 'marginBottom': '5px'}),
                                    dcc.Dropdown(
                                        id='structure-dropdown',
                                        options=structure_options,
                                        multi=True,
                                        value=[structure_options[0]['value']],
                                        style={'backgroundColor': '#333', 'color': '#000'}
                                    ),
                                ], style={'width': '300px', 'margin': '10px'}),
                            ], style={
                                'display': 'flex',
                                'justifyContent': 'center',
                                'alignItems': 'flex-start',
                                'padding': '15px',
                                'backgroundColor': 'rgba(0, 0, 0, 0.7)',
                                'borderRadius': '8px',
                                'margin': '10px auto',
                                'width': 'fit-content',
                                'zIndex': '2'
                            }),
                            html.Iframe(id='pydeck-new-map', srcDoc='', style={'width': '100%', 'height': '80vh'}),
                        ],
                        style={
                            'width': '98%', 'margin': '0 auto', 'backgroundColor': '#1a1a1a',
                            'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px', 'border': '2px solid #444',
                            'position': 'relative'
                        }
                    )
                ]
            )
        ],
        style={
            'width': '98%', 'margin': '0 auto', 'fontFamily': 'Roboto, sans-serif'
        },
        className='tabs-container'
    ),
    dcc.Store(id='gnaf-data-store'),
], style={'backgroundColor': 'black', 'minHeight': '100vh', 'margin': '0', 'padding': '0'})

@app.callback(
    Output('gnaf-data-store', 'data'),
    [Input('pydeck-map', 'clickInfo'),
     Input('search-bar', 'value')],
    prevent_initial_call=True
)
def load_gnaf_data(click_info, search_value):
    point_index = None
    state = None
    if click_info and 'object' in click_info and 'index' in click_info:
        point_index = click_info['index']
        selected_row = df.iloc[point_index]
        state = selected_row['State']
    elif search_value:
        search_value = search_value.strip()
        if search_value in df['AMSAssetRef'].values:
            point_index = df[df['AMSAssetRef'] == search_value].index[0]
            selected_row = df.iloc[point_index]
            state = selected_row['State']
    if state is None:
        return None
    gnaf_df = load_gnaf_dataframe(state)
    if gnaf_df.empty:
        return {'state': state, 'data': []}
    gnaf_data = gnaf_df.to_dict('records')
    return {'state': state, 'data': gnaf_data}

@app.callback(
    [Output('pydeck-map', 'data'),
     Output('pydeck-map', 'tooltip')],
    [Input('category-selector', 'value'),
     Input('search-bar', 'value')]
)
def update_map_and_tooltip(category, search_value):
    current_view_state = pdk.ViewState(
        latitude=-25.3,
        longitude=133.8,
        zoom=4,
        bearing=0,
        pitch=45
    )
    if search_value:
        search_value = search_value.strip()
        if search_value in df['AMSAssetRef'].values:
            selected_row = df[df['AMSAssetRef'] == search_value]
            lat = selected_row['Latitude'].iloc[0]
            lon = selected_row['Longitude'].iloc[0]
            current_view_state = pdk.ViewState(
                latitude=lat,
                longitude=lon,
                zoom=12,
                bearing=0,
                pitch=45
            )
    layer = create_layer(category)
    tooltip_text = {
        'corrosion_region_id': {
            "html": "<b>{SiteName}</b><br>{AMSAssetRef}</br><br>Height: {Height}m<br>Corrosion: {CorrosionRegionType}",
            "style": {"background": "grey", "color": "white", "font-family": '"Roboto", sans-serif', "z-index": "10000"}
        },
        'wind_region_id': {
            "html": "<b>{SiteName}</b><br>Height: {Height}m<br>Wind: {WindRegionType}",
            "style": {"background": "grey", "color": "white", "font-family": '"Roboto", sans-serif', "z-index": "10000"}
        },
        'snow_ice_id': {
            "html": "<b>{SiteName}</b><br>Height: {Height}m<br>Snow/Ice: {SnowIceRegion}",
            "style": {"background": "grey", "color": "white", "font-family": '"Roboto", sans-serif', "z-index": "10000"}
        },
        'PaintingType': {
            "html": "<b>{SiteName}</b><br>Height: {Height}m<br>Paint Type: {PaintingType}",
            "style": {"background": "grey", "color": "white", "font-family": '"Roboto", sans-serif', "z-index": "10000"}
        }
    }
    r = pdk.Deck(
        layers=[layer],
        initial_view_state=current_view_state,
        tooltip=tooltip_text[category],
        map_style=pdk.map_styles.DARK
    )
    return r.to_json(), tooltip_text[category]

@app.callback(
    Output('legend-container', 'children'),
    [Input('category-selector', 'value')]
)
def update_legend(category):
    legend_items = legend_data[category]
    return [
        html.H3("Legend", style={'color': 'white', 'marginBottom': '10px'}),
        html.Ul(
            children=[
                html.Li([
                    html.Span(
                        style={
                            'display': 'inline-block', 'width': '15px', 'height': '15px',
                            'backgroundColor': item['color'], 'marginRight': '10px', 'borderRadius': '3px'
                        }
                    ),
                    item['label']
                ], style={'marginBottom': '5px'}) for item in legend_items
            ],
            style={'listStyleType': 'none', 'padding': '0'}
        )
    ]

@app.callback(
    [
        Output('nearby-residences-container', 'style'),
        Output('nearby-residences-table', 'style'),
        Output('nearby-residences-table', 'children')
    ],
    [Input('pydeck-map', 'clickInfo'),
     Input('search-bar', 'value')],
    [State('gnaf-data-store', 'data')],
    prevent_initial_call=True
)
def update_nearby_residences(click_info, search_value, gnaf_store_data):
    nearby_container_default_style = {
        'margin': '0', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'border': '2px solid #444',
        'marginBottom': '20px', 'display': 'none'
    }
    nearby_table_default_style = {
        'width': '98%', 'overflowY': 'scroll', 'maxHeight': '30vh', 'backgroundColor': '#1a1a1a',
        'border': '2px solid white', 'color': 'white', 'padding': '10px', 'margin-bottom': '1.4%',
        'display': 'none'
    }
    default_nearby_content = html.Div(
        "No selection made. Click a point or search an AMS Asset Ref.",
        style={
            'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif',
            'padding': '20px', 'display': 'none'
        }
    )
    point_index = None
    selected_row = None
    state = None
    lat = None
    lon = None
    if click_info and 'object' in click_info and 'index' in click_info:
        point_index = click_info['index']
        selected_row = df.iloc[point_index]
        lat = selected_row['Latitude']
        lon = selected_row['Longitude']
        state = selected_row['State']
    elif search_value:
        search_value = search_value.strip()
        if search_value in df['AMSAssetRef'].values:
            point_index = df[df['AMSAssetRef'] == search_value].index[0]
            selected_row = df.iloc[point_index]
            lat = selected_row['Latitude']
            lon = selected_row['Longitude']
            state = selected_row['State']
    if point_index is None:
        return (
            nearby_container_default_style,
            nearby_table_default_style,
            default_nearby_content
        )
    nearby_container_visible_style = {
        'margin': '0', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'border': '2px solid #444',
        'marginBottom': '20px', 'display': 'block'
    }
    nearby_table_visible_style = {
        'width': '98%', 'overflowY': 'scroll', 'maxHeight': '30vh', 'backgroundColor': '#1a1a1a',
        'border': '2px solid white', 'color': 'white', 'padding': '10px', 'margin-bottom': '1.4%',
        'display': 'block'
    }
    if gnaf_store_data and gnaf_store_data.get('state') == state and gnaf_store_data.get('data'):
        gnaf_df = pd.DataFrame(gnaf_store_data['data'])
    else:
        gnaf_df = load_gnaf_dataframe(state)
    if gnaf_df.empty:
        nearby_table_content = html.Div(
            f"State: {state}. No GNAF data available or file not found.",
            style={
                'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif',
                'padding': '20px'
            }
        )
    else:
        gnaf_df['distance_meters'] = gnaf_df.apply(
            lambda row: haversine(lat, lon, row['LATITUDE'], row['LONGITUDE']),
            axis=1
        )
        nearby_residences = gnaf_df[gnaf_df['distance_meters'] <= 100]
        if nearby_residences.empty:
            nearby_table_content = html.Div(
                f"State: {state}. No residences found within 100 meters.",
                style={
                    'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif',
                    'padding': '20px'
                }
            )
        else:
            nearby_table_content = html.Table(
                children=[
                    html.Tr([
                        html.Th(col, style={
                            'color': '#ffffff', 'backgroundColor': '#333333', 'padding': '12px 15px',
                            'textAlign': 'left', 'fontFamily': 'Roboto, sans-serif', 'fontWeight': '500',
                            'borderBottom': '1px solid #444', 'whiteSpace': 'nowrap'
                        }) for col in ['ADDRESS_LABEL', 'FLAT_TYPE', 'distance_meters']
                    ])
                ] + [
                    html.Tr([
                        html.Td(str(row[col]) if pd.notnull(row[col]) else 'N/A', style={
                            'color': '#e0e0e0', 'backgroundColor': '#222222' if i % 2 == 0 else '#1a1a1a',
                            'padding': '12px 15px', 'fontFamily': 'Roboto, sans-serif',
                            'borderBottom': '1px solid #333', 'transition': 'background-color 0.2s ease'
                        }) for col in ['ADDRESS_LABEL', 'FLAT_TYPE', 'distance_meters']
                    ]) for i, (_, row) in enumerate(nearby_residences.iterrows())
                ],
                style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'}
            )
    nearby_table_with_hover = html.Div(
        nearby_table_content,
        style={'width': '100%'},
        className='table-container'
    )
    return (
        nearby_container_visible_style,
        nearby_table_visible_style,
        nearby_table_with_hover
    )

@app.callback(
    [
        Output('pydeck-map', 'style'),
        Output('table-container', 'style'),
        Output('data-table', 'style'),
        Output('data-table', 'children'),
        Output('plot-container', 'style'),
        Output('plot-container', 'children'),
        Output('satellite-container', 'style'),
        Output('satellite-map', 'figure'),
        Output('street-view-container', 'style'),
        Output('street-view-iframe', 'srcDoc'),
    ],
    [Input('pydeck-map', 'clickInfo'),
     Input('search-bar', 'value')],
    [State('gnaf-data-store', 'data')],
    prevent_initial_call=True
)
def update_layout(click_info, search_value, gnaf_store_data):
    map_default_style = {
        'display': 'inline-block', 'marginTop': '15%', 'width': '99%', 'height': '68vh',
        'verticalAlign': 'top', 'backgroundColor': 'black', 'border': '2px solid #444'
    }
    table_container_default_style = {
        'margin-right': '2%', 'marginTop': '1%', 'display': 'none', 'width': '43%',
        'verticalAlign': 'top', 'border': '2px solid white', 'backgroundColor': 'black'
    }
    table_default_style = {
        'overflowY': 'scroll', 'maxHeight': '57vh', 'backgroundColor': 'black',
        'border': '2px solid white', 'color': 'white', 'padding': '10px', 'display': 'none'
    }
    plot_default_style = {
        'width': '95%', 'margin': '0', 'display': 'none', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px', 'border': '2px solid #444'
    }
    satellite_container_default_style = {
        'width': '88%', 'margin-left': '5%', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginBottom': '20px',
        'border': '2px solid #444', 'display': 'none'
    }
    street_view_container_default_style = {
        'width': '88%', 'margin-left': '5%', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px',
        'border': '2px solid #444', 'display': 'none'
    }
    default_table_content = html.Div(
        "Click a point on the map or enter a valid AMS Asset Ref to view details.",
        style={
            'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif',
            'padding': '20px'
        }
    )
    default_plot_content = []
    default_satellite_figure = go.Figure()
    default_street_view_html = ""

    point_index = None
    selected_row = None
    ams_ref = None
    lat = None
    lon = None
    if click_info and 'object' in click_info and 'index' in click_info:
        point_index = click_info['index']
        selected_row = df.iloc[point_index]
        ams_ref = selected_row['AMSAssetRef']
        lat = selected_row['Latitude']
        lon = selected_row['Longitude']
    elif search_value:
        search_value = search_value.strip()
        if search_value in df['AMSAssetRef'].values:
            point_index = df[df['AMSAssetRef'] == search_value].index[0]
            selected_row = df.iloc[point_index]
            ams_ref = selected_row['AMSAssetRef']
            lat = selected_row['Latitude']
            lon = selected_row['Longitude']
    if point_index is None:
        return (
            map_default_style,
            table_container_default_style,
            table_default_style,
            default_table_content,
            plot_default_style,
            default_plot_content,
            satellite_container_default_style,
            default_satellite_figure,
            street_view_container_default_style,
            default_street_view_html
        )

    map_clicked_style = {
        'display': 'inline-block', 'marginTop': '15%', 'width': '68%', 'height': '68vh',
        'verticalAlign': 'top', 'backgroundColor': 'black', 'border': '2px solid #444',
        'transition': 'width 0.3s ease'
    }
    table_container_visible_style = {
        'margin-right': '2%', 'marginTop': '1%', 'display': 'inline-block', 'width': '43%',
        'verticalAlign': 'top', 'marginLeft': '2.5%', 'border': '2px solid #444',
        'backgroundColor': '#1a1a1a', 'borderRadius': '8px',
        'boxShadow': '0 4px 8px rgba(255, 255, 255, 0.1)', 'transition': 'width 0.3s ease, opacity 0.3s ease, margin 0.3s ease'
    }
    table_visible_style = {
        'overflowY': 'scroll', 'maxHeight': '57vh', 'backgroundColor': '#1a1a1a',
        'color': 'white', 'padding': '15px', 'display': 'block', 'width': '90%',
        'transition': 'max-height 0.3s ease, opacity 0.3s ease'
    }
    plot_visible_style = {
        'width': '95%', 'display': 'block', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px', 'border': '2px solid #444',
        'verticalAlign': 'top', 'transition': 'width 0.3s ease, opacity 0.3s ease, margin-top 0.3s ease'
    }
    satellite_container_visible_style = {
        'width': '88%', 'margin-left': '2%', 'display': 'block', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginBottom': '20px', 'border': '2px solid #444',
        'transition': 'width 0.3s ease, opacity 0.3s ease'
    }
    street_view_container_visible_style = {
        'width': '88%', 'margin-left': '2%', 'display': 'block', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px', 'border': '2px solid #444',
        'transition': 'width 0.3s ease, opacity 0.3s ease'
    }

    table = html.Table(
        children=[
            html.Tr([
                html.Th(col, style={
                    'color': '#ffffff', 'backgroundColor': '#333333', 'padding': '12px 15px',
                    'textAlign': 'left', 'fontFamily': 'Roboto, sans-serif', 'fontWeight': '500',
                    'borderBottom': '1px solid #444', 'whiteSpace': 'nowrap'
                }),
                html.Td(str(selected_row[col]) if pd.notnull(selected_row[col]) else 'N/A', style={
                    'color': '#e0e0e0', 'backgroundColor': '#222222' if i % 2 == 0 else '#1a1a1a',
                    'padding': '12px 15px', 'fontFamily': 'Roboto, sans-serif',
                    'borderBottom': '1px solid #333', 'transition': 'background-color 0.2s ease'
                })
            ]) for i, col in enumerate(selected_columns)
        ],
        style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'}
    )
    table_with_hover = html.Div(
        table,
        style={'width': '100%'},
        className='table-container'
    )
    structure_df = maintenance_df[maintenance_df['AMSAssetRef'] == ams_ref].copy()
    structure_df["Y_Value"] = structure_df["RiskRating_Cleaned"].map(lambda x: severity_levels.get(x, (-1, "black"))[0])
    structure_df["Color"] = structure_df["RiskRating_Cleaned"].map(lambda x: severity_levels.get(x, (-1, "black"))[1])
    structure_df = structure_df.dropna(subset=['IssueCreated', 'Y_Value'])
    y_ticks_labels = {v[0]: k for k, v in severity_levels.items()}
    maintenance_fig = px.scatter(
        structure_df,
        x="IssueCreated",
        y="Y_Value",
        hover_data={"IssueDescription": True, "IssueCreated": True, "Y_Value": False},
        labels={"IssueCreated": "Time (Issue Created)", "Y_Value": "Severity Level"},
        title=f"Maintenance Issues for {ams_ref}"
    )
    maintenance_fig.update_traces(
        marker=dict(
            color=structure_df['Color'],
            size=12,
            opacity=0.9,
            line=dict(width=1, color="black")
        )
    )
    maintenance_fig.update_layout(
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
            title="Time (Issue Created)",
            title_font=dict(color="white"),
            tickfont=dict(color="white"),
            showgrid=True,
            gridcolor="rgba(255,255,255,0.2)"
        ),
        template="plotly_dark",
        plot_bgcolor="#1a1a1a",
        paper_bgcolor="#1a1a1a",
        font=dict(color="white"),
        height=400,
        showlegend=False
    )
    corrosion_fig = go.Figure()
    years = np.arange(0, 11, 1)
    for component in components:
        metal_loss_values = np.linspace(component["metal_loss"], 0, len(years))
        label = f"{component['description']} ({component['part_no']})"
        corrosion_fig.add_trace(
            go.Scatter(
                x=years,
                y=metal_loss_values,
                mode="lines",
                name=label,
                line=dict(width=2),
            )
        )
    corrosion_fig.update_layout(
        title=f"Corrosion Metal Loss Depth (%) for {ams_ref}",
        xaxis_title="Time (Years)",
        yaxis_title="Metal Loss Depth (%)",
        xaxis=dict(range=[0, 10], tickvals=np.arange(0, 11, 1)),
        yaxis=dict(range=[0, 100], tickvals=np.arange(0, 101, 10)),
        legend=dict(
            x=1.05,
            y=1,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255, 255, 255, 0.5)",
            bordercolor="Black",
            borderwidth=1,
        ),
        template="plotly_dark",
        plot_bgcolor="#1a1a1a",
        paper_bgcolor="#1a1a1a",
        font=dict(color="white"),
        height=400,
        margin=dict(l=40, r=40, t=40, b=20)
    )
    plot_content = [
        html.H2("Maintenance and Corrosion Analysis", style={
            'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif', 'marginBottom': '10px'
        }),
        dcc.Graph(figure=maintenance_fig, style={'width': '100%', 'marginBottom': '20px'}),
        dcc.Graph(figure=corrosion_fig, style={'width': '100%'})
    ]
    satellite_fig = create_satellite_figure(lat, lon, selected_row['Height'])
    street_view_html = create_street_view_html(lat, lon)
    return (
        map_clicked_style,
        table_container_visible_style,
        table_visible_style,
        table_with_hover,
        plot_visible_style,
        plot_content,
        satellite_container_visible_style,
        satellite_fig,
        street_view_container_visible_style,
        street_view_html
    )

@app.callback(
    [
        Output('weather-container', 'style'),
        Output('weather-plots', 'children')
    ],
    [Input('pydeck-map', 'clickInfo'),
     Input('search-bar', 'value')],
    [State('gnaf-data-store', 'data')],
    prevent_initial_call=True
)
def update_weather(click_info, search_value, gnaf_store_data):
    weather_container_default_style = {
        'width': '98%', 'margin': '0 auto', 'display': 'none', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px'
    }
    default_weather_content = html.Div(
        "No air quality data available",
        style={'color': 'white', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif'}
    )
    point_index = None
    lat = None
    lon = None
    if click_info and 'object' in click_info and 'index' in click_info:
        point_index = click_info['index']
        selected_row = df.iloc[point_index]
        lat = selected_row['Latitude']
        lon = selected_row['Longitude']
    elif search_value:
        search_value = search_value.strip()
        if search_value in df['AMSAssetRef'].values:
            point_index = df[df['AMSAssetRef'] == search_value].index[0]
            selected_row = df.iloc[point_index]
            lat = selected_row['Latitude']
            lon = selected_row['Longitude']
    if point_index is None:
        return (
            weather_container_default_style,
            default_weather_content
        )
    weather_container_visible_style = {
        'width': '95%', 'margin': '0 auto', 'display': 'block', 'backgroundColor': '#1a1a1a',
        'padding': '10px', 'borderRadius': '8px', 'marginTop': '20px', 'border': '2px solid #444'
    }
    try:
        air_quality_df = fetch_air_quality_data(lat, lon)
        weather_df =  fetch_weather_data(lat, lon)
        weather_plots = create_weather_plots(weather_df,air_quality_df)
    except Exception as e:
        print(f"Error fetching air quality data: {e}")
        weather_plots = html.Div(
            f"Failed to load air quality data: {str(e)}",
            style={'color': 'red', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif'}
        )
    return (
        weather_container_visible_style,
        weather_plots
    )

@app.callback(
    Output('pydeck-new-map', 'srcDoc'),
    [Input('corrosion-dropdown', 'value'),
     Input('structure-dropdown', 'value')]
)
def update_new_map(corrosion_values, structure_values):
    corrosion_values = corrosion_values or []
    structure_values = structure_values or []
    filtered_df = df
    if corrosion_values:
        filtered_df = filtered_df[filtered_df['CorrosionRegionType'].isin(corrosion_values)]
    if structure_values:
        filtered_df = filtered_df[filtered_df['StructureClassCode'].isin(structure_values)]
    active_combinations = filtered_df['Combination'].unique()
    layer = create_layer_new_map(filtered_df)
    legend_html = create_legend_html(active_combinations, color_map)
    view_state = pdk.ViewState(latitude=-25.3, longitude=133.8, zoom=4, bearing=0, pitch=45)
    tooltip = {
        "html": "<b>{SiteName}</b><br>Height: {Height}m<br>Combination: {Combination}",
        "style": {"background": "grey", "color": "white", "font-family": "'Roboto', sans-serif", "z-index": "10000"}
    }
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=pdk.map_styles.DARK,
    )
    map_html = deck._repr_html_() + legend_html
    return map_html

if __name__ == '__main__':
    app.run_server(debug=True)