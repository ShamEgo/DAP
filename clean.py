import pandas as pd

file_path = r"D:\Documents\UTS\Code\Dash\ParallelCoordinatesBuilder\Structure Details_17March2025.xlsx"
sheet     = "Amplitel Structure Details"
out_path  = r"D:\Documents\UTS\Code\Dash\ParallelCoordinatesBuilder\parrallel_coordinates_all_info.csv"

# 1. Read & keep only the needed columns
keep = [
    "AMS Asset Ref",
    "Latitude",
    "Longitude",
    "State",
    "SnowIceRegion",
    "CorrosionRegionType",
    "StructureClassCode",
    "Height",
    "PaintingType",
    "StructureLoadPercentage",
    "InspectionFrequency"
]
df = pd.read_excel(file_path, sheet_name=sheet)[keep]

# 2. Drop missing rows & remove UNKNOWN classes
df = (
    df
    .dropna()
    .query('StructureClassCode != "UNKNOWN"')
)

# 3. Title-case your two text columns
df["StructureClassCode"] = df["StructureClassCode"].str.title()
df["PaintingType"]      = df["PaintingType"].str.title()

# 4. Remove any row where StructureLoadPercentage contains %, < or ,
mask = df["StructureLoadPercentage"].astype(str).str.contains(r"[%<,*`'>]")
df = df[~mask]

# 5. Rename the column
df = df.rename(columns={"AMS Asset Ref": "AMSAssetRef"})

# 6. Export to CSV
df.to_csv(out_path, index=False)
