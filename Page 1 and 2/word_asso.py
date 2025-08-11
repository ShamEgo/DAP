import pandas as pd
import numpy as np
import networkx as nx
import plotly.graph_objects as go
from dash import Dash, html, dcc

# Load CSV data
df = pd.read_csv('tower_components.csv', 
                 usecols=['AMSAssetRef', 'Component', 'CorrosionDescription', 'Height', 'CorrosionRegionType'],
                 dtype={'AMSAssetRef': str, 'Component': str, 'CorrosionDescription': str, 
                        'Height': float, 'CorrosionRegionType': str})

# Handle missing values
df.fillna({'CorrosionDescription': 'Unknown', 'Height': 0, 'Component': 'Unknown', 'CorrosionRegionType': 'Unknown'}, inplace=True)
df = df[df['AMSAssetRef'].notna()]

# Extract state
def extract_state(asset_ref):
    two_letter_states = ['WA', 'NT', 'SA']
    three_letter_states = ['NSW', 'VIC', 'QLD', 'TAS', 'ACT']
    if asset_ref[:2] in two_letter_states:
        return asset_ref[:2]
    elif asset_ref[:3] in three_letter_states:
        return asset_ref[:3]
    return 'Unknown'

df['State'] = df['AMSAssetRef'].apply(extract_state)

# Filter for NSW state
df = df[df['State'] == 'NSW']

# Define corrosion severity and region color mappings (aesthetic blue-white palette)
corrosion_severity = {
    "Heavy Corrosion": (3, "#ff0000"),    # Deep indigo
    "Bubbled Corrosion": (2.5, "#fffb00"), # Vibrant blue-purple
    "Signs of Corrosion": (2, "#006dfc"),  # Soft sky blue
    "Rust": (1.5, "#ff0000"),             # Pale lavender-blue
    "Light Corrosion": (1, "#f6ff00"),     # Very light blue
    "No Corrosion": (0, "#00ff15"),        # Crisp white-blue
    "Unknown": (0, "#ffffff")              # Muted slate
}
region_color_map = {
    "Coastal": "#ff0000",    # Rich navy
    "Inland": "#1eff00",     # Bright azure
    "Unknown": "#ffffff"     # Cool gray
}

# Create NetworkX graph
G = nx.Graph()

# Add tower nodes
for tower in df['AMSAssetRef'].unique():
    tower_row = df[df['AMSAssetRef'] == tower].iloc[0]
    G.add_node(tower, type='tower', Height=tower_row['Height'], 
               CorrosionRegionType=tower_row['CorrosionRegionType'], 
               State=tower_row['State'])

# Add component nodes and edges to towers
for _, row in df.iterrows():
    tower = row['AMSAssetRef']
    component = f"{row['AMSAssetRef']}_{row['Component']}"
    G.add_node(component, type='component', Component=row['Component'], 
               CorrosionDescription=row['CorrosionDescription'])
    G.add_edge(tower, component, weight=corrosion_severity.get(row['CorrosionDescription'], (0, "#94a3b8"))[0])

# Create 3D positions
supergraph = nx.star_graph(len(df['AMSAssetRef'].unique()))
superpos = nx.spring_layout(supergraph, dim=3, scale=6.0, seed=429)
pos = {}
towers = list(df['AMSAssetRef'].unique())
for i, (tower, center) in enumerate(zip(towers, list(superpos.values())[1:])):
    pos[tower] = center
    components = [n for n in G.nodes if G.nodes[n]['type'] == 'component' and n.startswith(tower)]
    if components:
        subgraph = nx.subgraph(G, components)
        subpos = nx.spring_layout(subgraph, dim=3, center=center, scale=1.5, seed=1430 + i)
        pos.update(subpos)

# Create edge traces
edge_traces = []
for u, v in G.edges():
    x0, y0, z0 = pos.get(u, (0, 0, 0))
    x1, y1, z1 = pos.get(v, (0, 0, 0))
    weight = G.edges[u, v]['weight']
    color = corrosion_severity.get(
        G.nodes[v]['CorrosionDescription'] if G.nodes[v]['type'] == 'component' else 'Unknown', 
        (0, "#94a3b8"))[1]
    edge_traces.append(go.Scatter3d(
        x=[x0, x1, None],
        y=[y0, y1, None],
        z=[z0, z1, None],
        mode='lines',
        line=dict(width=weight * 2, color=color),
        hoverinfo='none'
    ))

# Create node traces
node_traces = []
for tower in towers:
    x, y, z = pos[tower]
    height = G.nodes[tower]['Height']
    region = G.nodes[tower]['CorrosionRegionType']
    node_traces.append(go.Scatter3d(
        x=[x], y=[y], z=[z],
        mode='markers+text',
        text=[tower[:10]],
        textposition='top center',
        hovertext=[f"Asset: {tower}<br>Height: {height:.2f}m<br>Region: {region}<br>State: NSW"],
        hoverinfo='text',
        marker=dict(
            size=min(10 + height / 5, 30),
            color=region_color_map[region],
            line=dict(width=1, color='#e5e7eb'),
            opacity=0.9
        ),
        name=f"Tower: {tower[:10]}"
    ))
    components = [n for n in G.nodes if G.nodes[n]['type'] == 'component' and n.startswith(tower)]
    if components:
        comp_x = []
        comp_y = []
        comp_z = []
        comp_text = []
        comp_hovertext = []
        colors = []
        for node in components:
            x, y, z = pos[node]
            comp_x.append(x)
            comp_y.append(y)
            comp_z.append(z)
            comp_text.append(G.nodes[node]['Component'])
            comp_hovertext.append(f"Component: {G.nodes[node]['Component']}<br>Corrosion: {G.nodes[node]['CorrosionDescription']}")
            colors.append(corrosion_severity.get(G.nodes[node]['CorrosionDescription'], (0, "#94a3b8"))[1])
        node_traces.append(go.Scatter3d(
            x=comp_x, y=comp_y, z=comp_z,
            mode='markers+text',
            text=comp_text,
            textposition='top center',
            hovertext=comp_hovertext,
            hoverinfo='text',
            marker=dict(
                size=8,
                color=colors,
                line=dict(width=1, color='#e5e7eb'),
                opacity=0.8
            ),
            name=f"Components of {tower[:10]}"
        ))

# Create figure
fig = go.Figure(data=edge_traces + node_traces)
fig.update_layout(
    title=dict(
        text='3D Tower-Component Network (NSW Only)',
        x=0.5,
        xanchor='center',
        font=dict(size=24, color='#f3f4f6', family='Arial')
    ),
    showlegend=False,
    hovermode='closest',
    margin=dict(t=60, b=20, l=20, r=20),
    scene=dict(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', backgroundcolor="#000000"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', backgroundcolor="#000000"),
        zaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', backgroundcolor="#000000"),
        bgcolor="#000000",
        camera=dict(
            eye=dict(x=2, y=0, z=0.5),
            projection=dict(type='perspective'),
            up=dict(x=0, y=0, z=1)
        ),
        dragmode='orbit'
    ),
    plot_bgcolor='#000000',
    paper_bgcolor='#000000',
    font=dict(color='#f3f4f6', family='Arial')
)

# Initialize Dash app
app = Dash(__name__)

# Layout with only graph
app.layout = html.Div([
    dcc.Graph(id='3d-graph', figure=fig, style={'height': '100vh', 'width': '100vw'}),
], style={'backgroundColor': "#000000", 'height': '100vh', 'width': '100vw', 'margin': 0, 'padding': 0, 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden'})

# Run the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port = 8081, debug=True)
    #app.run(debug=True)