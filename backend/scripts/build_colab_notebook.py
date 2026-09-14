import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata.kernelspec = {"name": "python3", "display_name": "Python 3", "language": "python"}
nb.metadata.language_info = {"name": "python", "version": "3"}

cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# Module 1 - Multi-Hazard Red Zone Model (Google Colab)

**Purpose of the whole system**: score *every* village in India for 4 disasters
(flood, landslide, coastal erosion, cloudburst) and decide RED / ORANGE / GREEN.

This Colab notebook is the **self-contained** version of the model. It creates a
small demo district on the fly (fully offline), computes the 4 hazard scores,
fuses them, and trains the model - exactly like the project pipeline does.

**How to use**
1. `File > Save a copy in Drive`
2. `Runtime > Run all`
3. Outputs land in `sih_data/` (a folder created next to this notebook).

At the end, Step 4 shows how to swap in **real** India data (GFSM floods, ILSM
landslides, Copernicus DEM, etc.) - the code is identical.
"""
))

cells.append(nbf.v4.new_code_cell(
"""import subprocess, sys
for m in ("geopandas", "rasterio", "shapely", "pyproj"):
    try:
        __import__(m)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", m])
print("deps ok")
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## 0. Demo district configuration

Pick one template: **hill** (landslide + cloudburst heavy) or **coastal**
(flood + erosion heavy). Change `DEMO = "hill"` to `"coastal"` and re-run all.
"""
))

cells.append(nbf.v4.new_code_cell(
"""from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from rasterio.mask import mask as rio_mask
from rasterio.warp import transform_geom
from shapely.geometry import LineString, Polygon

BASE = Path("/content") if Path("/content").exists() else Path(".")
DATA = BASE / "sih_data"
DATA.mkdir(parents=True, exist_ok=True)

DEMO = "hill"  # try "coastal"

TEMPLATES = {
    # name: (lon_min, lat_min, lon_max, lat_max)
    "hill":    {"name": "Chamoli (hill)",    "bbox": (78.90, 29.60, 79.90, 30.60)},
    "coastal": {"name": "Kendrapara (coast)", "bbox": (86.30, 20.05, 87.25, 20.90)},
}
CFG = TEMPLATES[DEMO]
LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = CFG["bbox"]
CELL = 0.003
N_ROWS = max(10, int(round((LAT_MAX - LAT_MIN) / CELL)))
N_COLS = max(10, int(round((LON_MAX - LON_MIN) / CELL)))
RNG = np.random.default_rng(42)
N_VILLAGES = 150
print("demo district:", CFG["name"], "| grid", N_ROWS, "x", N_COLS)
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Step 1 - Build the demo district layers

This mirrors the **11-layer input list** your team chose. In this demo, layers
are generated realistically. In production each line is replaced by the real
raster (links in Step 4).

| # | Layer (your spec)            | Real source           | Demo cell output |
|---|------------------------------|-----------------------|------------------|
| 1 | Village boundaries           | Census / Survey of India | `villages.geojson` |
| 2 | DEM                          | Copernicus/SRTM 30m   | `dem.tif`          |
| 3 | Rainfall                     | CHIRPS / IMD          | `extreme_rain.tif` |
| 4 | Landslide susceptibility     | GSI/Bhuvan/ILSM       | `landslide.tif`    |
| 5 | Flood susceptibility         | GFSM                  | `flood.tif`        |
| 6 | Coastal erosion              | DSAS/shoreline data   | `coastline.geojson`|
| 7 | Cloudburst risk              | IMD + rainfall extremes | built from DEM fields |
| 8 | Drainage                     | HydroSHEDS            | `drainage.tif`     |
| 9 | Land cover                   | ESA WorldCover        | (Phase 2)          |
| 10| Population                   | Census 2011/WorldPop  | (Phase 2)          |
| 11| Admin boundaries (S-D-B-V)   | Census                | `district` column  |

"""
))

cells.append(nbf.v4.new_code_cell(
"""def _smooth(a, iters=8):
    x = a.astype(float)
    k = np.array([0.25, 0.5, 0.25])
    for _ in range(iters):
        x = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), axis=1, arr=x)
        x = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), axis=0, arr=x)
    return x

def _field(low, high):
    f = _smooth(RNG.uniform(0, 1, (N_ROWS, N_COLS)))
    span = f.max() - f.min()
    return low + (high - low) * (f - f.min()) / (span + 1e-9)

def _write_tif(path, arr):
    with rasterio.open(path, "w", driver="GTiff", height=N_ROWS, width=N_COLS,
                       count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(LON_MIN, LAT_MAX, CELL, CELL)) as dst:
        dst.write(arr.astype("float32"), 1)

# flood map: GFSM classes 1 (very low) .. 5 (very high)
_write_tif(DATA / "flood.tif", RNG.integers(1, 6, (N_ROWS, N_COLS)).astype(float))
# landslide probability 0..1 (ILSM-style)
_write_tif(DATA / "landslide.tif", _field(0.0, 1.0))
# drainage 0..1 and soil wetness TWI 4..24 (HydroSHEDS-style)
_write_tif(DATA / "drainage.tif", _field(0.0, 1.0))
_write_tif(DATA / "twi.tif", _field(4.0, 24.0))
# extreme rainfall days 0..6 (CHIRPS/IMD-style)
_write_tif(DATA / "extreme_rain.tif", _field(0.0, 6.0))
# DEM rises toward the north = hill template (south = delta/flat template)
lat_slope = np.linspace(2900.0 if DEMO == "hill" else 120.0,
                        300.0 if DEMO == "hill" else 50.0, N_ROWS)[:, None]
elev = lat_slope + RNG.normal(0, 60, (N_ROWS, N_COLS))
_write_tif(DATA / "dem.tif", elev)
grad = np.abs(np.gradient(elev, CELL)[0])
_write_tif(DATA / "slope.tif", _field(0.0, 40.0) + grad * 3.0)

# villages: 150 small polygons inside the box (Census-style)
lp, rp = np.array([LON_MIN + 0.01, LAT_MIN + 0.01]), np.array([LON_MAX - 0.01, LAT_MAX - 0.01])
geom = []
for i in range(N_VILLAGES):
    c = RNG.uniform(lp, rp)
    b = RNG.uniform(0.0003, 0.0006)
    geom.append(Polygon([c, (c[0] + b, c[1]), (c[0] + b, c[1] + b), (c[0], c[1] + b)]).buffer(0.0))
gdf = gpd.GeoDataFrame(
    {"village_id": [f"V-{i+1:03d}" for i in range(N_VILLAGES)],
     "name": [f"Sample Village {i+1}" for i in range(N_VILLAGES)],
     "district": [CFG["name"]] * N_VILLAGES,
     "geometry": geom}, crs="EPSG:4326")
gdf.to_file(DATA / "villages.geojson", driver="GeoJSON")

# coastline (erosion band measured from here)
coast = gpd.GeoDataFrame(
    {"geometry": [LineString([(LON_MIN, LAT_MIN + 0.02), (LON_MAX, LAT_MIN + 0.02)])]},
    crs="EPSG:4326")
coast.to_file(DATA / "coastline.geojson", driver="GeoJSON")

print("wrote to", DATA)
for f in sorted(DATA.glob("*")):
    print(" ", f.name)
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Step 2 - Score every village (4 hazard features)

For each village polygon we take the **zonal mean** of the hazard raster inside
the village, then normalise to 0-1:

- `flood_score`      = GFSM class (1-5) mapped to 0-1
- `landslide_score`  = ILSM probability 0-1
- `coastal_erosion_score` = 1.0 within 250 m of the coast, fading to 0 at 3 km
- `cloudburst_score` = weighted DEM + slope + drainage + TWI + extreme rainfall
"""
))

cells.append(nbf.v4.new_code_cell(
"""def clamp01(v):
    return max(0.0, min(1.0, float(v)))

def zonal_mean(path, geometry, source_crs=None):
    with rasterio.open(path) as src:
        geoms = [transform_geom(source_crs or src.crs, src.crs, geometry)]
        arr, _ = rio_mask(src, geoms, crop=True, all_touched=True, nodata=src.nodata)
        band = arr[0]
        if src.nodata is not None:
            band = band[band != src.nodata]
        band = band[np.isfinite(band)]
        return float(np.mean(band)) if band.size else float("nan")

df = gdf.copy()

df["flood_score"] = [clamp01((zonal_mean(DATA / "flood.tif", g) - 1) / 4) for g in df.geometry]
df["landslide_score"] = [clamp01(zonal_mean(DATA / "landslide.tif", g)) for g in df.geometry]

coast_line = gpd.read_file(DATA / "coastline.geojson").to_crs(epsg=3857).geometry.unary_union
dists = [g.centroid.distance(coast_line) for g in df.to_crs(epsg=3857).geometry]
df["coastal_erosion_score"] = [1.0 if d <= 250 else float(max(0.0, 1.0 - (d - 250) / 2750)) for d in dists]

CB_NORM = {"dem": 2500.0, "slope": 45.0, "drainage": 1.0, "twi": 25.0, "extreme_rain": 5.0}
CB_W = {"dem": 0.20, "slope": 0.25, "drainage": 0.20, "twi": 0.15, "extreme_rain": 0.20}
raw = {k: [zonal_mean(DATA / (k + ".tif"), g) for g in df.geometry] for k in CB_W}
cb = {k: [clamp01(v / CB_NORM[k]) if np.isfinite(v) else np.nan for v in raw[k]] for k in CB_W}
df["cloudburst_score"] = sum(CB_W[k] * np.array(cb[k]) for k in CB_W)

df[["village_id", "district", "flood_score", "landslide_score",
    "coastal_erosion_score", "cloudburst_score"]].head()
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Step 3 - Fusion engine + Red Zone

1. **AHP baseline**: expert weights fuse the 4 scores into a **Multi-Hazard
   Score** (0-1) -> Risk Category -> RED / ORANGE / GREEN.
2. **Learned model**: Random Forest + Logistic Regression learn the pattern from
   a *label* ("this village got hit / safe"). Until real NDRF records are
   attached, we use a clear placeholder rule (Very High OR high on flood AND
   landslide). Swap `LABELS_CSV` in the training cell with real records later.

Outputs: `fusion_model.joblib` (trained model) + `village_redzone.csv`
(village-wise risk table for the map).
"""
))

cells.append(nbf.v4.new_code_cell(
"""WEIGHTS = {"flood": 0.30, "landslide": 0.30, "cloudburst": 0.20, "coastal": 0.20}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

df["mh_ahp"] = (WEIGHTS["flood"] * df["flood_score"]
                + WEIGHTS["landslide"] * df["landslide_score"]
                + WEIGHTS["cloudburst"] * df["cloudburst_score"]
                + WEIGHTS["coastal"] * df["coastal_erosion_score"]).clip(0, 1)

def category(score):
    return ["Low", "Moderate", "High", "Very High"][
        int(score >= 0.75) + int(score >= 0.50) + int(score >= 0.25)]

def redzone(cat):
    return {"Very High": "RED", "High": "ORANGE",
            "Moderate": "GREEN", "Low": "GREEN"}[cat]

df["risk_category"] = df["mh_ahp"].apply(category)
df["red_zone_status"] = df["risk_category"].apply(redzone)
df[["village_id", "mh_ahp", "risk_category", "red_zone_status"]]
"""
))

cells.append(nbf.v4.new_code_cell(
"""from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, classification_report
import joblib

FEATURES = ["flood_score", "landslide_score", "coastal_erosion_score", "cloudburst_score"]

LABELS_CSV = None  # point this at real NDRF records (with village_id + disaster_flag) when available

def build_labels(d):
    if LABELS_CSV is not None:
        rec = pd.read_csv(LABELS_CSV)
        m = d.merge(rec[["village_id", "disaster_flag"]], on="village_id", how="left")
        m["disaster_flag"] = m["disaster_flag"].fillna(0).astype(int)
        return m["disaster_flag"].values
    return ((d["mh_ahp"] >= 0.55) |
            ((d["flood_score"] >= 0.55) & (d["landslide_score"] >= 0.55))).astype(int).values

df["label"] = build_labels(df)
print("positive labels:", int(df["label"].sum()), "of", len(df))

X = df[FEATURES].values
y = df["label"].values
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

models = {
    "RandomForest": RandomForestClassifier(n_estimators=300, max_depth=6, random_state=42),
    "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
}
scores = {}
for name, est in models.items():
    a = cross_val_score(est, X_train, y_train, cv=5, scoring="roc_auc")
    scores[name] = a.mean()
    print(f"{name}: CV ROC-AUC = {a.mean():.3f} (+/- {a.std():.3f})")
best_name = max(scores, key=scores.get)
print("best model:", best_name)

best = models[best_name]
best.fit(X_train, y_train)
pred = best.predict_proba(X_test)[:, 1]
print("Test ROC-AUC:", round(roc_auc_score(y_test, pred), 3))
print(classification_report(y_test, best.predict(X_test), target_names=["safe", "hit"]))
if hasattr(best, "feature_importances_"):
    print("feature importances:")
    for f, i in zip(FEATURES, best.feature_importances_):
        print(f"  {f:28s} {i:.3f}")

joblib.dump(best, DATA / "fusion_model.joblib")
df[["village_id", "name", "district", *FEATURES, "mh_ahp", "risk_category",
    "red_zone_status", "label"]].to_csv(DATA / "village_redzone.csv", index=False)
print("saved:", DATA / "village_redzone.csv", "and", DATA / "fusion_model.joblib")
"""
))

cells.append(nbf.v4.new_code_cell(
"""df.groupby("red_zone_status").agg(
    villages=("village_id", "count"), avg_risk=("mh_ahp", "mean")).round(3)
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Step 4 - Go national (REAL data swap)

The model above is **identical** to the one that answers all of India. Modify
three things and re-run from Step 2:

1. **Village layer**: upload the Census/SoI village GeoJSON and load it:
   `villages = gpd.read_file("/content/villages_india.geojson")`
2. **Hazard rasters**: replace the generated `flood.tif`, `landslide.tif`,
   `dem.tif`, `slope.tif`, `drainage.tif`, `twi.tif`, `extreme_rain.tif` with
   the real national tiles (same names, same folder, same code).
3. **Coastline**: swap `coastline.geojson` for the real Natural Earth / DSAS line.

One pipeline, one output table, 6.4 lakh villages. For speed, run the loop
state-by-state (same code) and concatenate.

### Where each real layer comes from
| Layer | Free download |
|---|---|
| Flood | GFSM `projects/floodsus/assets/fsm_ei5` (Earth Engine) |
| Landslide | ILSM `projects/ee-nirdeshsharmanith1/assets/ILSM_probability` (EE) |
| DEM/slope | Copernicus 30 m on AWS (s3://copernicus-dem-30m) |
| Drainage | HydroSHEDS free tiles |
| Rainfall extremes | CHIRPS or IMD gridded data |
| Coastline | Natural Earth public GeoJSON |
| Villages | Census village boundaries (VIKSAT / data.gov.in) |
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Input / Output recap

**Input (per district):** village polygons + 7 rasters + coastline (the 11-layer
list in Step 1).

**Process:** per village -> 4 hazard scores -> weighted Multi-Hazard Score ->
Risk Category (Low / Moderate / High / Very High) -> RED / ORANGE / GREEN.

**Output:** `village_redzone.csv` - one row per village with the Multi-Hazard
Score, category, and zone. This is the village-wise risk table the dashboard
map and the relocation-priority module read next.
"""
))

nb["cells"] = cells
nbf.write(nb, "backend/Training_Module1_Colab.ipynb")
print("notebook written: backend/Training_Module1_Colab.ipynb")