import pandas as pd
import matplotlib.pyplot as plt

# --- CONFIG -------------------------------------------------------------
file_path  = r"Structure Details_17March2025.xlsx"     # update if needed
sheet_name = "Amplitel Structure Details"              # update if needed
# -----------------------------------------------------------------------

# 1. Load data
df = pd.read_excel(file_path, sheet_name=sheet_name)

# 2. Aggregate: unique towers per structure class
counts = (
    df.groupby("StructureClassCode")["AMSAssetRef"]
      .nunique()
      .sort_values(ascending=False)
)

# 3. Plot
fig, ax = plt.subplots(figsize=(10, 6))
counts.plot(kind="bar", ax=ax)

ax.set_title("Number of Towers by Structure Class")
ax.set_xlabel("Structure Class")
ax.set_ylabel("Number of Towers")
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")

# 4. Annotate each bar with its value
for patch in ax.patches:
    height = patch.get_height()
    ax.annotate(f"{int(height)}",
                (patch.get_x() + patch.get_width() / 2, height),
                ha="center", va="bottom", fontsize=9, xytext=(0, 3),
                textcoords="offset points")  # 3-point vertical offset

plt.tight_layout()
plt.show()
# plt.savefig("towers_by_class.png", dpi=300)
