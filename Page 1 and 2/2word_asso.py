import pandas as pd
import numpy as np
import matplotlib.colors as mcolors
import plotly.graph_objects as go
from dash import Dash, html, dcc, Output, Input

# ─── 1. Load & preprocess ──────────────────────────────────────────────────────
df = pd.read_excel(
    'tower_steel_classified.xlsx',
    usecols=[
        'StructureClassCode','component','frequency','Part',
        'Amplitel Structure','Amplitel Site','Customer owned'
    ],
    dtype=str
).fillna('')

df['frequency'] = pd.to_numeric(df['frequency'], errors='coerce').fillna(0)
df['owner_type'] = df.apply(
    lambda r: 'Amplitel' if (r['Amplitel Structure'] or r['Amplitel Site']) else 'Customer',
    axis=1
)
df['category'] = df.apply(
    lambda r: r['Amplitel Structure'] if r['owner_type']=='Amplitel' else 'Customer Owned',
    axis=1
)

# ─── 2. Build two gradients ────────────────────────────────────────────────────
def make_gradient(c1, c2, steps=100):
    a, b = np.array(mcolors.to_rgb(c1)), np.array(mcolors.to_rgb(c2))
    return [mcolors.to_hex(a + (b-a)*(i/(steps-1))) for i in range(steps)]

blue_grad   = make_gradient('#deebf7', '#08519c', 100)   # light→dark blue
pink_grad   = make_gradient('#fde0dd', '#c51b8a', 100)   # light→dark pink

min_f, max_f = df['frequency'].min(), df['frequency'].max()

def pick_color(freq, owner):
    # map freq to index 0–99
    if max_f>min_f:
        idx = int((freq - min_f)/(max_f-min_f)*99)
    else:
        idx = 49
    idx = max(0, min(99, idx))
    return blue_grad[idx] if owner=='Amplitel' else pink_grad[idx]

df['color'] = df.apply(lambda r: pick_color(r['frequency'], r['owner_type']), axis=1)

# ─── 3. Layout & callbacks ─────────────────────────────────────────────────────
classes = ['All'] + sorted(df['StructureClassCode'].unique())

def make_sunburst(class_code):
    dff = df if class_code=='All' else df[df['StructureClassCode']==class_code]
    total = int(dff['frequency'].sum())
    
    # prepare labels/parents/values/colors
    labels, parents, values, colors = [], [], [], []
    # inner ring: categories
    for cat, grp in dff.groupby('category'):
        labels.append(cat)
        parents.append('')
        val = int(grp['frequency'].sum())
        values.append(val)
        # pick a mid-tone
        mid = 50
        colors.append(blue_grad[mid] if cat!='Customer Owned' else pink_grad[mid])
    # outer ring: components
    for _, row in dff.iterrows():
        labels.append(row['component'])
        parents.append(row['category'])
        values.append(int(row['frequency']))
        colors.append(row['color'])
    
    fig = go.Figure(go.Sunburst(
        labels=labels,
        parents=parents,
        values=values,
        branchvalues='total',
        marker=dict(
            colors=colors,
            line=dict(color='white', width=2)
        ),
        hovertemplate='<b>%{label}</b><br>Freq: %{value}<extra></extra>',
        insidetextorientation='radial',
        sort=False,
        maxdepth=2,
        hole=0.4
    ))
    # central label
    fig.add_annotation(
        dict(text=f"<b>{total}</b><br>Total",
             x=0.5, y=0.5, showarrow=False,
             font=dict(size=20, color='white'))
    )
    fig.update_layout(
        margin=dict(t=50,b=20,l=20,r=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    return fig

app = Dash(__name__)
app.layout = html.Div([
    html.Div([
        html.Label("Structure class:"),
        dcc.Dropdown(classes, 'All', id='class-dd', style={'width':'300px'})
    ], style={'padding':'10px','backgroundColor':'#f0f0f0'}),
    dcc.Graph(id='sunburst', style={'height':'80vh'}),
], style={'fontFamily':'Arial'})

@app.callback(
    Output('sunburst','figure'),
    Input('class-dd','value')
)
def update(sb_class):
    return make_sunburst(sb_class)

if __name__=='__main__':
    app.run_server(debug=True)
