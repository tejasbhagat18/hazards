# How to Add a New State/District (Module 1)

Follow these steps to add ANY new state and district to the platform. The 2 demo
districts (Chamoli + Kendrapara) are already processed; this is the recipe to
extend to more states.

---

## Step 0 — Prerequisites

- District-level village boundaries come from `VILLAGE_SHP_DIR` — by default
  `<your home>\Downloads\indian_village_boundries\` (or point the env var at a
  custom folder). If your state is missing, download its Survey-of-India village
  shapefile and place it in that folder.
- Use the district **LGD code** / exact district spelling as it appears in the
  shapefile's `District` column (ALL CAPS).

---

## Step 1 — Preprocess the village boundaries

Open PowerShell in the project root and run:

```powershell
python -m backend.data_pipeline.preprocess_villages --state UTTARAKHAND --district CHAMOLI
```

- `--state` = shapefile name WITHOUT `.shp` (e.g. `UTTARAKHAND`, `ODISHA`, `WEST_BENGAL`)
- `--district` = exact district name in ALL CAPS (e.g. `CHAMOLI`, `KENDRAPARA`)
- `--state-name` = display name used in the dashboard (e.g. `Uttarakhand`) [optional]

This writes `backend/data/processed/village_boundaries_<district>.geojson`
(filtered to that district, reprojected to EPSG:4326).

If you get an error listing "Available: [...]", use one of those district names.

---

## Step 2 — Export the hazard rasters from Google Earth Engine

Open [Google Earth Engine Code Editor](https://code.earthengine.google.com), make
sure the project is your own registered project id (`GEE_PROJECT`), then paste and
run the script below. It creates Tasks that download, for your district, the 3
heavy layers (CHIRPS rainfall, GFSM flood, ILSM landslide) that are too big for
the normal API path.

```javascript
// SIH 2026 - Export hazard layers for an INDIVIDUAL state/district
// EDIT THESE TWO LINES for your new district:
var DISTRICT = "chamoli";                              // lower-case district key
var REGION = ee.Geometry.Rectangle([LON_MIN, LAT_MIN, LON_MAX, LAT_MAX]); // district bbox (lon, lat)

// CHIRPS rainfall mean 2023-2025
var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
  .filterBounds(REGION).filterDate('2023-01-01','2025-12-31')
  .select('precipitation').mean().clip(REGION);
Export.image.toDrive({image: chirps, description: 'chirps_rainfall_' + DISTRICT,
  folder: 'sih_gee', scale: 60, crs: 'EPSG:4326', region: REGION, maxPixels: 1e9});

// GFSM flood susceptibility (set GEE_ASSET_FLOOD_GFSM to your hosted version)
var gfsm = ee.ImageCollection('GEE_ASSET_FLOOD_GFSM | your flood susceptibility image collection id').mosaic().clip(REGION);
Export.image.toDrive({image: gfsm, description: 'flood_gfsm_' + DISTRICT,
  folder: 'sih_gee', scale: 60, crs: 'EPSG:4326', region: REGION, maxPixels: 1e9});

// ILSM landslide probability (set GEE_ASSET_LANDSLIDE_ILSM to your hosted version)
var ilsm = ee.Image('GEE_ASSET_LANDSLIDE_ILSM | your landslide probability image id').clip(REGION);
Export.image.toDrive({image: ilsm, description: 'ilsm_' + DISTRICT,
  folder: 'sih_gee', scale: 60, crs: 'EPSG:4326', region: REGION, maxPixels: 1e9});
```

**To find your district bbox:** run this in the code editor —
```javascript
print(ee.Geometry.Point([CENTRAL_LON, CENTRAL_LAT]).bounds().coordinates().getInfo());
```
or approximate it; the exact bbox is not critical (a little extra is fine).

**Wait for Tasks:** in the Tasks tab, wait until each task shows `Completed`.
Then download from Google Drive folder `sih_gee/` and save into
`backend/data/raw/` with these EXACT names (remove the `_0`/`_1` suffix GEE adds):

```
chirps_rainfall_<district>.tif
flood_gfsm_<district>.tif
ilsm_<district>.tif
```

---

## Step 3 — Run the pipeline (auto-downloads DEM. GPM)

From the project root (PowerShell):

```powershell
python -m backend.gee.run_gee --state <STATE_NAME> --district <district>
```

- `--state` = display state (e.g. `Uttarakhand`, `Odisha`)
- `--district` = lower-case district key (e.g. `chamoli`)

The pipeline will:
1. Load the village boundaries you preprocessed
2. Download SRTM DEM + slope + GPM rainfall itself (they fit in the API)
3. Reuse your manually-exported CHIRPS / GFSM / ILSM rasters
4. Score all 4 hazards -> multi-hazard fusion -> Red Zone
5. Save `village_risk_<district>.csv` + `village_risk_<district>.geojson` +
   8 hazard/red-zone rasters into `backend/data/processed/` and `backend/data/gee_output/`

> **First-time only:** if the district is not a coastal state, no coastline step runs.
> If it IS coastal, the pipeline falls back to the local `coastline.geojson`.

---

## Step 4 — Verify

```powershell
python -c "import pandas as pd; df=pd.read_csv('backend/data/processed/village_risk_<district>.csv'); print(df[['flood_score','landslide_score','coastal_erosion_score','cloudburst_score','multi_hazard']].describe().round(3)); print(df['red_zone_status'].value_counts())"
```

You should see one row per village with 4 hazard scores and a red-zone distribution.

---

## Step 5 — It appears in the dashboard automatically

The FastAPI backend **auto-discovers** any `village_risk_<district>.csv` /
`village_risk_<district>.geojson` in the data folders. Just refresh the web app —
your new district shows up in the state list with zero code changes.

---

## Checklist

- [ ] Shapefile present in `Downloads\indian_village_boundries`
- [ ] Ran `preprocess_villages.py` -> `village_boundaries_<district>.geojson` OK
- [ ] Tasks completed & 3 tifs placed in `backend/data/raw` with exact names
- [ ] `run_gee.py` completed all 10 steps with no ERROR
- [ ] `village_risk_<district>.geojson` + `.csv` exist and look sensible
- [ ] Dashboard refresh shows the new district