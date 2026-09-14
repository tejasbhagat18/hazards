# SIH 2026 — Module 1 (Hazard Intelligence) Complete Workflow

**Project:** Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations
**Problem ID:** SIH PS 26191 (RDX010) | **Ministry:** Ministry of Home Affairs / NDRF
**Team:** Multi-Hazard Red Zone & Relocation Intelligence Platform
**Demo states:** Uttarakhand (Chamoli — flood, landslide, cloudburst) & Odisha (Kendrapara — flood, coastal erosion)

---

## 1. What is Module 1?

Module 1 = **Hazard Intelligence.** It converts raw geospatial + satellite data into a
*village-level* answer to the question:

> "Which habitation (village) sits in a dangerous zone for a flood / landslide /
> coastal erosion / cloudburst, and how severe is that danger?"

The result is a **Red Zone map + a ranked village list**, which is the input for
Modules 2 (Exposure & Vulnerability), 3 (Relocation Intelligence) and 4 (Dashboard).

---

## 2. Big picture — how the platform is built

```
MODULE 1  Hazard Intelligence   ->  every village gets 4 hazard scores -> Red Zone
MODULE 2  Exposure & Vulnerability -> population, livelihoods, carrying capacity
MODULE 3  Relocation Intelligence  -> Safer site recommendation + relocation priority
MODULE 4  Integrated GIS Dashboard -> interactive Leaflet map + tables (React)
```

Module 1 is **complete and working** (see Section 9 for actual results).

Analysis unit = **village** (Survey of India village polygons). The smallest
administrative unit at which charity-relocation decisions are made.

---

## 3. Data sources (with links)

### 3.1 Village boundaries (the analysis unit)
Survey of India / Census village polygons (LCC_WGS84, reprojected to EPSG:4326).
Local files used in this project:

| State | File | Village count |
|---|---|---|
| Uttarakhand | `UTTARAKHAND.shp` | Chamoli filter = **1,237 villages** |
| Odisha | `ODISHA.shp` | Kendrapara filter = **1,555 villages** |

> These are official village boundary layers (village = smallest census revenue village,
> keyed by LGD code `Vill_LGD`).

### 3.2 Hazard datasets (all fetched from Google Earth Engine)

| Hazard | Dataset name | GEE asset ID | What it gives us |
|---|---|---|---|
| Flood | GFSM (Global Flood Susceptibility Map) | `projects/floodsus/assets/fsm_ei5` | Global flood-susceptibility class (1–5) per pixel — **how flood-prone** a location is |
| Landslide | ILSM (Integrated Landslide Susceptibility Model) | `projects/ee-nirdeshsharmanith1/assets/ILSM_probability` | Global landslide **probability (0–1)** per pixel |
| Terrain (all) | SRTM 30 m DEM | `USGS/SRTMGL1_003` | Elevation → used for slope, flood/landslide/cloudburst |
| Rainfall | GPM IMERG monthly | `NASA/GPM_L3/IMERG_MONTHLY_V07` | Mean rainfall mm/hr |
| Rainfall | CHIRPS daily (2023–2025 mean) | `UCSB-CHG/CHIRPS/DAILY` | Mean rainfall mm/day → extreme-rainfall index |
| Drainage | HydroSHEDS | `WWF/HydroSHEDS/03VFDEM` | Stream network / flow (cloudburst input) |
| Coastline (Odisha) | Natural Earth coastline (local GeoJSON fallback) | `NGDC/OSD` broken → local `coastline.geojson` | Distance to coastline → coastal erosion |
| (future) | WorldPop population | `WorldPop/GP/100m/pop` | Module 2 exposure |
| (future) | ESA WorldCover | `ESA/WorldCover/v100` | Land cover |

> Google Earth Engine is a **free cloud platform** with petabytes of pre-processed
> satellite + climate data — no downloading of raw satellite scenes needed.

---

## 4. How each hazard is detected (the 4 hazard engines)

Every hazard engine does the same 2-step idea:
**(A)** fetch the relevant layers from GEE, **(B)** extract the average value *inside
each village polygon* (zonal statistics) and turn it into a **0–1 danger score**.

### 4.1 FLOOD engine — `backend/hazards/flood.py` + `gee/pipeline.py step4`
1. Get **GFSM** flood-susceptibility raster (class 1 = none, 5 = very high) for the district area.
2. Compute a terrain-based flood index from DEM + slope + rainfall as a secondary signal.
3. Take the **maximum** of the two.
4. Normalise the GFSM class (1→0, 5→1): `flood_score = clip((class − 1) / 4, 0, 1)`.
5. Average inside each village → `flood_score` (0–1).

### 4.2 LANDSLIDE engine — `backend/hazards/landslide.py` + `step5`
1. Get **ILSM** landslide-probability raster (0–1).
2. Add a topographic secondary index (slope, elevation, rain).
3. Take the **maximum** of the two.
4. Average inside each village → `landslide_score` (0–1).

### 4.3 COASTAL EROSION engine — `backend/hazards/coastal.py` + `step7`
1. Load coastline geometry.
2. Reproject villages + coastline to Web Mercator (EPSG:3857, metres) so distances are real.
3. Distance from each village centroid to the coast.
4. Distance → score:
   - `≤ 250 m` → **1.0** (hard risk zone)
   - `250 m – 3 km` → linear decay to 0
   - `> 3 km` → **0.0**
5. `coastal_erosion_score` (0–1). *(Chamoli is inland → 0; Kendrapara gets real coastal values.)*

### 4.4 CLOUDBURST engine — `backend/hazards/cloudburst.py` + `step6`
Cloudburst is a *flash-rain + steep-terrain* event, so it combines 5 layers with expert weights:

| Layer | Normalisation | Weight |
|---|---|---|
| Elevation (DEM) | /2500 m | 0.20 |
| Slope | /45° | 0.25 |
| Drainage (stream density) | /1.0 | 0.20 |
| TWI (wetness) | /25 | 0.15 |
| Extreme rainfall (GPM+CHIRPS anomaly) | /5 | 0.20 |

`cloudburst_score = Σ (weight × normalised layer)` → **0–1**.

---

## 5. Village-level aggregation (zonal statistics)

In `step8_village_aggregation`, for every village polygon we compute the **average
value of the raster cells that intersect that polygon** (`zonal_mean` in
`backend/hazards/base.py`). Result: a table with one row per village:

```
village_id | name | district | state
flood_score | landslide_score | cloudburst_score | coastal_erosion_score
dem | slope
```

- Chamoli: **1,237 rows**, Kendrapara: **1,555 rows**.
- This table is saved as `backend/data/processed/village_risk_<district>.csv`.

---

## 6. Multi-Hazard fusion (integrated model)

`backend/fusion/red_zone.py` + `backend/Fusion_and_RedZone.ipynb`

### 6.1 AHP-style expert weights (baseline — the active method)
Weights derived from expert pairwise comparisons (weighted sum, normalised to 1):

| Hazard | Weight |
|---|---|
| Flood | 0.35 |
| Landslide | 0.30 |
| Coastal erosion | 0.20 |
| Cloudburst | 0.15 |

```
multi_hazard = 0.35·flood + 0.30·landslide + 0.20·coastal + 0.15·cloudburst   (clipped 0–1)
```

### 6.2 Risk category + Red Zone rule

| multi_hazard | Category | Red Zone |
|---|---|---|
| < 0.25 | Low | **GREEN** |
| 0.25 – 0.50 | Moderate | **YELLOW** |
| 0.50 – 0.75 | High | **ORANGE** |
| ≥ 0.75 | Very High | **RED** |

### 6.3 Machine-Learning variant (Method B — trained model)
Trained in the notebook (Random Forest 300 trees vs Logistic Regression, 5-fold CV
ROC-AUC, stratified 75/25 split):
1. **Features:** the 4 hazard scores (`flood`, `landslide`, `coastal`, `cloudburst`).
2. **Labels:** villages actually hit by a disaster in NDRF/state records (`1` = hit). Until
   real records exist, a clearly-documented placeholder label is generated (Very High AHP
   score, or high flood AND high landslide).
3. Model learns the **non-linear best combination** of the 4 scores.
4. Outputs `model_risk` (probability of being hit) next to the explainable AHP score.
5. The AHP score remains the *active* explainable output; the ML model takes over once
   real NDRF labels are loaded (set `LABELS_CSV` in the notebook).

> Why both? AHP = transparent & judge-friendly (explainable AI), ML = self-learned
> weights. They agree on ~most villages; both columns are shown in the dashboard.

---

## 7. End-to-end pipeline steps (`backend/gee/pipeline.py`)

| Step | What happens | GEE asset |
|---|---|---|
| 1 | Village boundary load (SoI/LGD shapefile) | local .shp → GeoJSON |
| 2 | DEM + slope (60 m grid) | USGS/SRTMGL1_003 |
| 3 | Rainfall (GPM + CHIRPS mean, 2020–2025) | IMERG_MONTHLY_V07 + CHIRPS/DAILY |
| 4 | Flood risk | projects/floodsus GFSM |
| 5 | Landslide risk | ee-nirdeshsharmanith1 ILSM |
| 6 | Cloudburst risk (DEM+slope+drainage+TWI+rain) | HydroSHEDS etc. |
| 7 | Coastal erosion (distance to coastline) | local coastline.geojson (NGDC/OSD fallback) |
| 8 | Village-wise aggregation (zonal mean) | — |
| 9 | Multi-hazard fusion → Red Zone | — |
| 10 | Export CSV + GeoJSON + rasters | — |

---

## 8. Manual workflow (what we did by hand + browser export)

Because some GEE layers are too large for the API's 50 MB in-line download, the heavy
layers were exported via the **Earth Engine Code Editor** (browser) to Google Drive:

1. Open https://code.earthengine.google.com → login → select project `tejas-470510`.
2. Run an export script (see `gee/run_gee.py` / manual script below) that creates Tasks for:
   - CHIRPS rainfall (2023–2025 mean), GFSM flood, ILSM landslide — for **both** districts at **60 m**, EPSG:4326.
3. Each Task runs in the background (1–5 min), then files land in Google Drive → `sih_gee/`.
4. Download the 6 `.tif` files into `backend/data/raw/` (exact names, e.g. `ilsm_chamoli.tif`).
5. Run the pipeline **without `--force`** so it re-uses those manually-exported rasters and
   skips the heavy re-downloads:
   ```
   python -m backend.gee.run_gee --state Uttarakhand --district chamoli
   python -m backend.gee.run_gee --state Odisha --district kendrapara
   ```

DEM, slope, GPM rainfall download fine via the normal API path (auto fallback 30 m → 60 m
when a layer exceeds Earth Engine's 50 MB response cap).

---

## 9. ACTUAL OUTPUTS (Module 1 complete — run with real data)

### 9.1 Chamoli district (Uttarakhand) — hill district, landslide-dominated
- Villages scored: **1,237**
- **Red Zone distribution: ORANGE 747, YELLOW 490**
- Mean hazard scores: flood 0.639, landslide 0.879, cloudburst 0.282, coastal 0.000
- Mean multi-hazard: 0.530

### 9.2 Kendrapara district (Odisha) — coastal, flood-dominated
- Villages scored: **1,555**
- **Red Zone distribution: YELLOW 708, GREEN 847**
- Mean hazard scores: flood 0.595, landslide 0.064, cloudburst 0.010, coastal 0.011
  (coastal reaches 1.0 for shoreline villages like SATAVAYA, KHARINASI)
- Mean multi-hazard: 0.231

---

## 10. Files & folders (what you hand over)

```
backend/
  config/            settings, .env (GEE project tejas-470510)
  hazards/           the 4 scorers + zonal-statistics base
  gee/               pipeline.py (10 steps), run_gee.py, config.py
  fusion/            red_zone.py (AHP fusion + red zone rules)
  data_pipeline/     preprocess_villages.py (shapefile → GeoJSON)
  data/raw/          real rasters (DEM, GPM, CHIRPS, GFSM, ILSM, coastline)
  data/processed/    village_risk_chamoli.csv, village_risk_kendrapara.csv,
                     village_boundaries_<district>.geojson
  data/gee_output/   village_risk_<district>.geojson + 8 score/red-zone rasters
  data/output/       fusion_model.joblib, village_redzone.csv
  Fusion_and_RedZone.ipynb      training notebook (ML variant)
  Training_Module1_Colab.ipynb  end-to-end classroom notebook
```

---

## 11. How to present this to your leader (30-second pitch)

- **Input:** official village polygons + free satellite/climate data (GEE).
- **Engine:** 4 hazard models (flood/landslide/coastal/cloudburst), each producing a
  0–1 danger score per village.
- **Fusion:** AHP expert weights (explainable) + a trained Random Forest/Logistic model
  (self-learning), both mapped to GREEN / YELLOW / ORANGE / RED.
- **Output form:** per-village table + interactive map + ranked relocation priority list.
- **Done so far:** Module 1 complete for **2 demo districts** with real data — 1,237
  Chamoli villages and 1,555 Kendrapara villages classified into Red Zones.