#!/usr/bin/env python3

import csv
import json
from distutils import dir_util
import random
from sys import argv
from collections import OrderedDict
import argparse
from pathlib import Path

csvName = 'Public.csv'
groupColumn = 'Institution'
ordinals = []
excludes = []

if len(argv) > 2:
    csvName = argv[1]
    groupColumn = argv[2]
else:
    print(f"Usage: {argv[0]} <csv file> <group Column name> OPTIONS")
    print("OPTIONS are one of:")
    print("[ --excludes 'cat1, cat2, ...' ]")
    print("[ --cardinals 'cat1, cat2, ...' ]")
    print("[ --ordinals 'cat1, cat2, ...' ]")
    print("unlisted columns types are determined by the value of the first item. number = cardinal, string = ordinal")
    print(f"Example: {argv[0]} Public.csv 'Institution'")
    exit(1)

parser = argparse.ArgumentParser(description="Process some arguments.")

parser.add_argument(
    '--excludes',
    type=lambda s: [item.strip() for item in s.split(',')],
    help='Comma-separated list of column names to exclude'
)

parser.add_argument(
    '--ordinals',
    type=lambda s: [item.strip() for item in s.split(',')],
    help='Comma-separated list of column names to define as ordinals'
)

parser.add_argument(
    '--cardinals',
    type=lambda s: [item.strip() for item in s.split(',')],
    help='Comma-separated list of column names to define as cardinals'
)

parser.add_argument(
    '--corr-order',
    type=lambda s: [item.strip() for item in s.split(',')],
    help='(Optional) explicit order for CorrosionRegionType; defaults to the standard A..F list'
)

parser.add_argument(
    '-name',
    type=str,
    help='A sample name argument'
)

args = parser.parse_args(argv[3:])

print(f"Using {csvName} file and '{groupColumn}' as Group")

# === Canonical order for CorrosionRegionType (can be overridden via --corr-order) ===
CORR_FIELD = 'CorrosionRegionType'
DEFAULT_CORR_ORDER = [
    "A (Very Low)",
    "B (Low)",
    "C (Medium)",
    "D (High)",
    "E (Very High)",
    "F (Inland Tropical)"
]
CORR_ORDER = args.corr_order if args.corr_order else DEFAULT_CORR_ORDER
corr_index = {name: i for i, name in enumerate(CORR_ORDER)}

# Normalisation map (handles case/spaces/minor variants)
# Keys are lowercased/stripped; values are canonical labels above.
corr_normalise = {
    "a (very low)": "A (Very Low)",
    "b (low)": "B (Low)",
    "c (medium)": "C (Medium)",
    "d (high)": "D (High)",
    "e (very high)": "E (Very High)",
    "f (inland tropical)": "F (Inland Tropical)",
    # common loose variants:
    "very low": "A (Very Low)",
    "low": "B (Low)",
    "medium": "C (Medium)",
    "high": "D (High)",
    "very high": "E (Very High)",
    "inland tropical": "F (Inland Tropical)",
    "f (inland  tropical)": "F (Inland Tropical)",  # double space hedge
}

# Prepare output dir from csv stem
path = Path(csvName).with_suffix('').name
baseDir = Path(path)  # e.g., "Public"
dir_util.mkpath(str(baseDir))
dir_util.copy_tree('./template', str(baseDir))
print(f"Copied files to folder {path}..")

groups = []
firstRow = {}

files_dir = baseDir / 'files'
files_dir.mkdir(parents=True, exist_ok=True)

# === Read CSV, normalise corrosion labels, buffer rows, then sort by CORR_ORDER ===
buffered_rows = []
with open(csvName, 'r', encoding='utf-8-sig', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    print(reader.fieldnames)

    for row in reader:
        if not firstRow:
            firstRow = dict(row)  # snapshot original types

        # Collect unique group values
        gval = row.get(groupColumn, '')
        if gval not in groups:
            groups.append(gval)

        # Normalise CorrosionRegionType (case-insensitive)
        if CORR_FIELD in row and row[CORR_FIELD] is not None:
            key = str(row[CORR_FIELD]).strip().lower()
            row[CORR_FIELD] = corr_normalise.get(key, row[CORR_FIELD])

        # Preserve header order -> OrderedDict
        od = OrderedDict()
        for field in reader.fieldnames:
            od[field] = row.get(field, "")
        buffered_rows.append(od)

# Sort rows so the first occurrence order of categories follows CORR_ORDER
# (Helps D3 ordinal axes that infer domain order from data appearance.)
def corr_sort_key(r):
    label = r.get(CORR_FIELD, "")
    return corr_index.get(label, 9999)  # unknowns at end

buffered_rows.sort(key=corr_sort_key)

# Write data.js
data_js_path = files_dir / 'data.js'
with open(data_js_path, 'w', encoding='utf-8') as jsonfile:
    jsonfile.write('var dataJSON = [\n')
    for od in buffered_rows:
        json.dump(od, jsonfile, ensure_ascii=False)
        jsonfile.write(',\n')
    jsonfile.write('];\n')

print(f"Wrote new json file {data_js_path}")

def replace_in_file(filename: Path, placeholder: str, replacement: str):
    """Simple placeholder replacement using pure Python (cross-platform)."""
    p = Path(filename)
    text = p.read_text(encoding='utf-8')
    text = text.replace(placeholder, replacement)
    p.write_text(text, encoding='utf-8')

# Determine ordinals automatically (unless forced), based on first row
for key, value in firstRow.items():
    try:
        if args.ordinals and key in args.ordinals:
            print("Ordinal (Forced)", key, value)
            ordinals.append(key)
        elif args.cardinals and key in args.cardinals:
            print("Cardinal (Forced)", key, value)
            # do not append to ordinals
        else:
            float(value)
            print("Cardinal", key, value)
    except (ValueError, TypeError):
        print("Ordinal", key, value)
        ordinals.append(key)

# Ensure corrosion field is treated as ordinal
if CORR_FIELD not in ordinals:
    ordinals.append(CORR_FIELD)

print("Excluding:")
if args.excludes:
    excludes = args.excludes
for a in excludes:
    print('  ' + a)

# Generate colors for all group values
colors = {}
for g in groups:
    colors[g] = '#%06x' % random.randint(0, 0xFFFFFF)

# Prepare replacements
index_html = baseDir / 'index.html'
pc_js = files_dir / 'parallel-coordinates.js'

colors_js = json.dumps(colors) + ';'
groups_js = json.dumps(groups) + ';'
group_name = groupColumn
ordinals_js = json.dumps(ordinals)
excludes_js = json.dumps(excludes if excludes else [])

# Do replacements
replace_in_file(index_html, '_COLOURS_', colors_js)
replace_in_file(index_html, '_TITLE_', Path(path).name)
replace_in_file(index_html, '_GROUPS_', groups_js)
replace_in_file(index_html, '_GROUP_', group_name)

replace_in_file(pc_js, '_ORDINALS_', ordinals_js)
replace_in_file(pc_js, '_EXCLUDES_', excludes_js)
replace_in_file(pc_js, '_GROUP_', group_name)

print("Saved to: " + str(baseDir))
