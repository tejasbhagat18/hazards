# Backend — SIH 2026 RS1261 Multi-Hazard Intelligence Engine

Pipeline that converts hazard data into a village-level Red Zone table.

```
backend/
  config/          paths + free credential slots (config/.env, Phase 5)
  hazards/         the 4 danger sensors
    flood.py           GFSM flood map        -> flood_score  (0-1)
    landslide.py       ILSM landslide map    -> landslide_score (0-1)
    coastal.py         distance-to-coast + erosion band -> coastal_erosion_score (0-1)
    cloudburst.py      terrain + extreme rainfall -> cloudburst_score (0-1)
  gee/               Earth Engine pipeline for Module 1
    config.py          GEE assets, project config, hazard weights
    pipeline.py        Main pipeline class (10 steps)
    run_gee.py         CLI runner for the EE pipeline
    register_assets.py Register GEE ImageAssets from local rasters
    quickstart.py      Quick start script
  fusion/red_zone.py  integrated-model logic: 4 scores -> Multi-Hazard
                       -> Risk Category -> Red Zone (RED/ORANGE/GREEN)
  data_pipeline/download_data.py  real-data downloader
  scripts/build_notebook.py       rebuilds Fusion_and_RedZone.ipynb
  Fusion_and_RedZone.ipynb        THE training notebook (open in Jupyter)
  sample_data/        offline sample generator (no API keys needed)
  data/sample/        synthetic rasters + villages (fallback)
  data/raw/           REAL data downloaded here (takes priority)
  run_pipeline.py     end-to-end: rasters -> 4 scores -> red zone table
```

## Setup

```
pip install -r requirements.txt
```

## 1. Earth Engine Pipeline (Recommended)

The GEE pipeline generates all hazard rasters directly from Google Earth Engine assets and produces village-level Red Zone classification.

### Quick Start

```bash
# Uttarakhand (landslide + cloudburst)
python backend/gee/run_gee.py --state Uttarakhand --district chamoli

# Odisha (flood + coastal erosion)
python backend/gee/run_gee.py --state Odisha --district kendrapara

# Run both demo states
python backend/gee/run_gee.py --all-states

# Force re-download all GEE assets
python backend/gee/run_gee.py --state Uttarakhand --force
```

### Quick Start Script

```bash
python backend/gee/quickstart.py --state Uttarakhand
```

### How It Works

The pipeline runs 10 steps:

| Step | Module | GEE Assets Used |
|------|--------|-----------------|
| 1 | Village Layer Import | Survey of India village boundaries |
| 2 | DEM Layer | SRTM/Copernicus 30m |
| 3 | Rainfall Layer | GPM IMERG + CHIRPS |
| 4 | Flood Risk | GFSM + DEM + slope + rainfall |
| 5 | Landslide Risk | ILSM + slope + DEM + rainfall |
| 6 | Cloudburst Risk | DEM + slope + drainage + TWI + extreme rainfall |
| 7 | Coastal Erosion Risk | Shoreline data (Odisha/Maharashtra only) |
| 8 | Village-wise Aggregation | Zonal statistics per village polygon |
| 9 | Red Zone Generation | Multi-Hazard Score -> Risk Category -> RED/ORANGE/YELLOW |
| 10 | Export | CSV + GeoJSON + hazard rasters |

### GEE Assets Used

Public datasets (no personal project ties):

- **DEM**: `USGS/SRTMGL1_003` (SRTM 30m)
- **Rainfall**: `NASA/GPM_L3/IMERG_MONTHLY_V07`, `UCSB-CHG/CHIRPS/DAILY`
- **Population**: `WorldPop/GP/100m/pop`
- **Land Cover**: `ESA/WorldCover/v100`
- **Coastline**: `NGDC/OSD` (local `coastline.geojson` fallback)

The flood and landslide susceptibility layers are user-provided. Point the
environment variables below at the image ids you host or subscribe to in Earth
Engine (no hard-coded defaults are shipped).

### Environment Variables

```env
GEE_PROJECT=                # your registered Earth Engine project id
GEE_CREDENTIALS=            # path to service account JSON (optional)
GEE_ASSET_FLOOD_GFSM=       # flood susceptibility ImageCollection id
GEE_ASSET_LANDSLIDE_ILSM=   # landslide susceptibility Image id
GEE_VILLAGE_ASSET=          # village boundaries FeatureCollection id (optional; falls back to local GeoJSON)
USE_GEE=false               # set to true to use GEE in run_pipeline.py
SIH_DISTRICT=chamoli
GEE_ASSET_PREFIX=           # e.g. projects/<your-project>/assets/sih
```

### Register GEE Assets

After downloading rasters, register them as GEE ImageAssets for dashboard sharing:

```bash
python backend/gee/register_assets.py --state Uttarakhand --district chamoli
python backend/gee/register_assets.py --all-states
```

## Google Colab version (no setup, runs in browser)

`backend/Training_Module1_Colab.ipynb` is self-contained: it generates its own demo district, runs the full scoring + fusion + training, and writes `village_redzone.csv` to a local folder. To run it:

1. Open https://colab.research.google.com
2. **File > Upload notebook** and pick `Training_Module1_Colab.ipynb`
3. **Runtime > Run all**

It ends with a "Step 4 - Go national" section explaining exactly which variables to point at real national layers (Census villages, GFSM, ILSM, DEM, HydroSHEDS, CHIRPS, Natural Earth coastline).

## Districts

Set the active district with the `SIH_DISTRICT` environment variable:

```
$env:SIH_DISTRICT='chamoli'      # or 'kendrapara'
python backend/run_pipeline.py
```

Real layers per district (from the downloader + GEE):
- `backend/data/raw/{flood,ilsm,dem,slope}_{chamoli,kendrapara}.tif`
- `.env.example`/`GEE_PROJECT` stores your registered Earth Engine project id
- Output: `backend/data/processed/village_risk_{district}.csv`

Real records file (NDRF / state disaster incidents) can replace the notebook's placeholder labels: set `LABELS_CSV` inside `Fusion_and_RedZone.ipynb`.

## 2. Quick run

```
python backend/run_pipeline.py            # produces backend/data/processed/village_risk.csv
```

## 3. Train the integrated model (notebook)

```
jupyter notebook backend/Fusion_and_RedZone.ipynb
```

Rebuild it after edits to this repo: `python backend/scripts/build_notebook.py`.
It trains RF + LogisticRegression, compares against the AHP baseline, then saves:

- `backend/data/output/fusion_model.joblib`  — trained integrated model
- `backend/data/output/village_redzone.csv`  — final Module 1 table for the dashboard