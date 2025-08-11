import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk

# ──────────────────────────────────────────────────────────────
# 1. Load and clean data
# ──────────────────────────────────────────────────────────────

# List of AMS IDs to filter

#Replacements

ams_ids = [
    "NSW006626_STR_1", "NSW006626_STR_1", "NSW006626_STR_1",
    "NSW006626_STR_1", "NSW006626_STR_1", "NSW006626_STR_2",
    "NSW006626_STR_2", "NSW006626_STR_2", "NSW006626_STR_2",
    "NSW006626_STR_2", "QLD002766_STR_1", "QLD004829_STR_1",
    "QLD004829_STR_1", "QLD004829_STR_1", "QLD004992_STR_1",
    "QLD004994_STR_1", "QLD005699_STR_1",
    "QLD005699_STR_1", "QLD005699_STR_1", "QLD005755_STR_1",
    "QLD005755_STR_1", "QLD005755_STR_1", "QLD005755_STR_1",
    "QLD005755_STR_1", "TAS007886_STR_1", "VIC007312_STR_1",
    "WA001044_STR_1", "WA001044_STR_1", "WA001044_STR_1",
    "WA001373_STR_1", "WA001623_STR_1", "WA001628_STR_1",
    "WA001628_STR_1", "WA001628_STR_1", "WA001628_STR_1",
    "WA001628_STR_1", "WA001628_STR_1", "WA001631_STR_1"
]
'''

# Refurbishments
ams_ids = [
    "QLD004817_STR_1", "QLD004796_STR_1", "QLD005931_STR_1", "WA001055_STR_1",
    "TAS007886_STR_1", "TAS007869_STR_1", "QLD005309_STR_1",
    "VIC007768_STR_1", "QLD005623_STR_1", "QLD005472_STR_1", "QLD005284_STR_1",
    "WA001270_STR_1", "WA001076_STR_1", "WA001420_STR_1", "QLD002766_STR_1",
    "WA001114_STR_1", "NSW006646_STR_2",
     "QLD004906_STR_1", "QLD005628_STR_1", "SA000419_STR_1",
    "SA000355_STR_1", "VIC007554_STR_1", "QLD005851_STR_1",  "NSW006762_STR_1", "QLD004967_STR_1", "QLD005238_STR_1", "WA001376_STR_1",
    "NSW006612_STR_1", "QLD005315_STR_1", "QLD005447_STR_1", "NSW006535_STR_1",
     "VIC007312_STR_1", "WA001623_STR_1", "NT000824_STR_1",
    "TAS007901_STR_1", "QLD005876_STR_1", "QLD005183_STR_1",
    "QLD005585_STR_1", "QLD004829_STR_1", "QLD005619_STR_1",
    "NSW006823_STR_1", "QLD005207_STR_1", "QLD005618_STR_1", "QLD004858_STR_1",
    "QLD005031_STR_1", "QLD005770_STR_1", "NSW006646_STR_1", "NSW006907_STR_1", "NSW006463_STR_1",

]
'''
issues_df = pd.read_excel("Structure Maintenance Issues_17March2025.xlsx", sheet_name="Maintenance Issues")
issues_df.columns = [col.strip() for col in issues_df.columns]
issues_df['IssueCreated'] = pd.to_datetime(issues_df['IssueCreated'], dayfirst=True, errors='coerce')
issues_df = issues_df[issues_df['AMS Structure Asset Ref'].isin(ams_ids)]
issues_df = issues_df.sort_values(by='IssueCreated')

structure_df = pd.read_excel("Structure Details_17March2025.xlsx", sheet_name="Amplitel Structure Details")
structure_df.columns = [col.strip() for col in structure_df.columns]
meta_cols = [
    'AMSAssetRef', 'StructureClassCode', 'StructureInstallationDate',
    'CorrosionRegionType', 'WindRegionType', 'SnowIceRegion'
]
structure_meta = structure_df[meta_cols].drop_duplicates().set_index('AMSAssetRef')

unique_ids = sorted(issues_df['AMS Structure Asset Ref'].unique())
index = [0]  # mutable so we can update it inside handlers

# ──────────────────────────────────────────────────────────────
# 2. GUI Setup
# ──────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("Maintenance Issues Viewer")

fig, ax = plt.subplots(figsize=(12, 8))
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack()

def render_plot(idx):
    ax.clear()
    ams_id = unique_ids[idx]
    group = issues_df[issues_df['AMS Structure Asset Ref'] == ams_id]

    # Get structure metadata
    if ams_id in structure_meta.index:
        meta = structure_meta.loc[ams_id]
        meta_text = (
            f"Class: {meta['StructureClassCode']} | "
            f"Installed: {pd.to_datetime(meta['StructureInstallationDate'], errors='coerce').strftime('%Y-%m-%d') if pd.notnull(meta['StructureInstallationDate']) else 'Unknown'} | "
            f"Corrosion: {meta['CorrosionRegionType']} | "
            f"Wind: {meta['WindRegionType']} | "
            f"Snow/Ice: {meta['SnowIceRegion']}"
        )
    else:
        meta_text = "Structure metadata not found."

    lines = [f"{meta_text}\n\nIssues for {ams_id}:\n"]
    for _, row in group.iterrows():
        date = row['IssueCreated'].strftime("%Y-%m-%d") if pd.notnull(row['IssueCreated']) else "Unknown Date"
        desc = str(row['IssueDescription'])
        lines.append(f"{date}: {desc}")
    
    full_text = "\n".join(lines)
    ax.axis("off")
    ax.set_title(f"{ams_id}", fontsize=14, weight='bold')
    ax.text(0.01, 0.98, full_text, verticalalignment='top', horizontalalignment='left',
            wrap=True, fontsize=10, transform=ax.transAxes)
    canvas.draw()

def next_plot():
    if index[0] < len(unique_ids) - 1:
        index[0] += 1
        render_plot(index[0])

def prev_plot():
    if index[0] > 0:
        index[0] -= 1
        render_plot(index[0])

def exit_app():
    root.destroy()

# ──────────────────────────────────────────────────────────────
# 3. Buttons
# ──────────────────────────────────────────────────────────────
btn_frame = tk.Frame(root)
btn_frame.pack(pady=10)

tk.Button(btn_frame, text="Previous", command=prev_plot, width=12).grid(row=0, column=0, padx=10)
tk.Button(btn_frame, text="Next", command=next_plot, width=12).grid(row=0, column=1, padx=10)
tk.Button(btn_frame, text="Exit", command=exit_app, width=12).grid(row=0, column=2, padx=10)

# ──────────────────────────────────────────────────────────────
# 4. Initial plot
# ──────────────────────────────────────────────────────────────
render_plot(index[0])
root.mainloop()