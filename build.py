import csv
import json
from distutils import dir_util
import random
from sys import argv
from pathlib import Path

# ── Locate script & template dirs ───────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR / 'template'

# Command-line arguments
csvName     = 'parallel_coord.csv'
groupColumn = 'AMSAssetRef'
excludes    = []

if len(argv) > 1 and len(argv) <= 2:
    print(f"Usage: {argv[0]} <csv file> <group Column name> [columns to omit, ...]")
    print(f"Example: {argv[0]} Public.csv 'Institution' 'name'")
    exit(1)
elif len(argv) > 2:
    csvName     = argv[1]
    groupColumn = argv[2]
    excludes    = argv[3:]

print(f"Using {csvName!r} file and '{groupColumn}' as Group")
if excludes:
    print(f"Excluding columns: {', '.join(excludes)}")
print()

# ── Use pathlib for robust path handling ─────────────────────────────────────────
# CSV is alongside this script
csvPath = SCRIPT_DIR / csvName
if not csvPath.exists():
    raise FileNotFoundError(f"CSV not found at {csvPath!r}")

path    = csvPath.stem
baseDir = SCRIPT_DIR.parent / path      # create output next to builder folder
baseDir.mkdir(exist_ok=True)

# Copy the template directory into the output folder
dir_util.copy_tree(str(TEMPLATE_DIR), str(baseDir))
print(f"Copied files to folder {baseDir}")

groups   = []
firstRow = {}

# Read CSV and write JSON
with open(csvPath, newline='', encoding='utf-8') as csvfile, \
     open(baseDir / 'files' / 'data.js', 'w', encoding='utf-8') as jsonfile:
    reader = csv.DictReader(csvfile)
    jsonfile.write('var dataJSON = [')
    for row in reader:
        if not firstRow:
            firstRow = row.copy()
        if row[groupColumn] not in groups:
            groups.append(row[groupColumn])
        json.dump(row, jsonfile)
        jsonfile.write(',\n')
    jsonfile.write(']')

print(f"Wrote new json file {baseDir / 'files' / 'data.js'}\n")




# Replace function using Python instead of sed
def replace(s1, s2, filename):
    filename = Path(filename)
    content  = filename.read_text(encoding='utf-8')
    filename.write_text(content.replace(s1, s2), encoding='utf-8')


# right after you detect firstRow, before your replace() calls:

axis_order = [
    "State",
    "StructureClassCode",
    "Height",
    "SnowIceRegion",        # or whatever your exact header is
    "CorrosionRegionType",
    "PaintingType",
    "StructureLoadPercentage",
    "InspectionFrequency"         # or your exact “load frequcny” column name

]

# filter out any excludes, just in case
axis_order = [c for c in axis_order if c in firstRow and c not in excludes]

# now inject that order into your JS
replace('DIMENSIONS', json.dumps(axis_order), baseDir / 'files' / 'parallel-coordinates.js')


# Detect column types
print("Detected column types:")
ordinals = []
for key, value in firstRow.items():
    try:
        float(value)
        print(f"Numeric {key} {value}")
    except ValueError:
        print(f"Ordinal {key} {value}")
        ordinals.append(key)

# Generate colors
colors = {i: f'#{random.randint(0, 0xFFFFFF):06x}' for i in groups}

# Replace placeholders in files
replace('COLORS',   json.dumps(colors) + ';',                 baseDir / 'index.html')
replace('TITLE',    path,                                     baseDir / 'index.html')
replace('GROUPS',   json.dumps(groups) + ';',                 baseDir / 'index.html')
replace('GROUP',    groupColumn,                              baseDir / 'index.html')
replace('ORDINALS', json.dumps(ordinals),                     baseDir / 'files' / 'parallel-coordinates.js')
replace('EXCLUDES', json.dumps(excludes),                     baseDir / 'files' / 'parallel-coordinates.js')
replace('GROUP',    groupColumn,                              baseDir / 'files' / 'parallel-coordinates.js')

print(f"Saved to: {baseDir}")
