import pandas as pd
import re
import math

INPUT_FILE  = "fixtures/raw_text.csv"
OUTPUT_FILE = "exports/openings_final.csv"

# Load raw text
df_raw = pd.read_csv(INPUT_FILE)

# ── Patterns ──────────────────────────────────────────────
DIAMETER_CHARS = r'[oO\xf8\xd8∅]'

pat_ddb_rnd   = re.compile(rf'DDB\s*{DIAMETER_CHARS}\s*(\d+)', re.IGNORECASE)
pat_ddb_rect  = re.compile(r'DDB\s*(\d+)\s*/\s*(\d+)', re.IGNORECASE)
pat_wdb_rect  = re.compile(r'WDB\s+(\d+)\s*/\s*(\d+)', re.IGNORECASE)
pat_wdb_rnd   = re.compile(rf'WDB\s*{DIAMETER_CHARS}\s*(\d+)', re.IGNORECASE)
pat_uzdb_rect = re.compile(r'UZDB\s*(\d+)\s*/\s*(\d+)', re.IGNORECASE)
pat_uzdb_rnd  = re.compile(rf'UZDB\s*{DIAMETER_CHARS}\s*(\d+)', re.IGNORECASE)
pat_d         = re.compile(r'd\s*=\s*(\d+)\s*cm', re.IGNORECASE)

# ── Extract openings ──────────────────────────────────────
openings = []
for _, row in df_raw.iterrows():
    t = row["text"]
    base = {"filename": row["filename"], "x0": row["x0"], "y0": row["y0"]}

    for m in pat_ddb_rnd.finditer(t):
        d = int(m.group(1))
        openings.append({**base, "type": "Ceiling", "geometry": "round",
                         "length_cm": d, "width_cm": d})
    for m in pat_ddb_rect.finditer(t):
        openings.append({**base, "type": "Ceiling", "geometry": "rectangular",
                         "length_cm": int(m.group(1)), "width_cm": int(m.group(2))})
    for m in pat_wdb_rect.finditer(t):
        openings.append({**base, "type": "Wall", "geometry": "rectangular",
                         "length_cm": int(m.group(1)), "width_cm": int(m.group(2))})
    for m in pat_wdb_rnd.finditer(t):
        d = int(m.group(1))
        openings.append({**base, "type": "Wall", "geometry": "round",
                         "length_cm": d, "width_cm": d})
    for m in pat_uzdb_rect.finditer(t):
        openings.append({**base, "type": "UZDB", "geometry": "rectangular",
                         "length_cm": int(m.group(1)), "width_cm": int(m.group(2))})
    for m in pat_uzdb_rnd.finditer(t):
        d = int(m.group(1))
        openings.append({**base, "type": "UZDB", "geometry": "round",
                         "length_cm": d, "width_cm": d})

df = pd.DataFrame(openings)

# ── Extract d= values and assign nearest ─────────────────
d_vals = []
for _, row in df_raw.iterrows():
    for m in pat_d.finditer(str(row["text"])):
        d_vals.append({"filename": row["filename"],
                       "height_cm": float(m.group(1)),
                       "x0": row["x0"], "y0": row["y0"]})
df_d = pd.DataFrame(d_vals)

def nearest_d(row):
    sub = df_d[df_d["filename"] == row["filename"]]
    if sub.empty:
        return None
    dist = ((sub["x0"] - row["x0"])**2 + (sub["y0"] - row["y0"])**2)**0.5
    return sub.loc[dist.idxmin(), "height_cm"]

df["height_cm"] = df.apply(nearest_d, axis=1)

# ── Calculate weight ──────────────────────────────────────
DENSITY_KG_M3 = 440  # 3D-printed concrete shell effective density (matches server/app/models.py)

def weight(row):
    try:
        l, w, h = row["length_cm"]/100, row["width_cm"]/100, row["height_cm"]/100
        vol = math.pi * (l/2)**2 * h if row["geometry"] == "round" else l * w * h
        return round(vol * DENSITY_KG_M3, 1)
    except:
        return None

df["weight_kg"] = df.apply(weight, axis=1)

# ── Group identical openings and count ────────────────────
group_cols = ["filename", "type", "geometry", "length_cm", "width_cm", "height_cm", "weight_kg"]
df_grouped = (df.groupby(group_cols)
                .size()
                .reset_index(name="number"))

# ── Final format matching the target table ────────────────
df_grouped["floor"]     = "U1"
df_grouped["plan_name"] = "BFS_88160_A_T_5_" + df_grouped["filename"] + "_06"

final = df_grouped[[
    "floor", "plan_name",
    "length_cm", "width_cm", "height_cm",
    "geometry", "type", "number", "weight_kg"
]]
final.columns = [
    "Floor", "Construction phase/Plan name",
    "Length / cm", "Width / cm", "Height / cm",
    "Geometry", "Type", "Number", "Weight / kg"
]

final.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
print(f"Done! {len(final)} unique opening types saved to {OUTPUT_FILE}")
print(final.head(10).to_string(index=False))
