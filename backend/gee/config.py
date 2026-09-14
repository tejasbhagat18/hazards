import os
from pathlib import Path

import geopandas as gpd

BASE_DIR = Path(__file__).resolve().parents[1]

GEE_PROJECT = os.getenv("GEE_PROJECT", "tejas-470510")

ASSETS = {
    "dem": "USGS/SRTMGL1_003",
    "population": "WorldPop/GP/100m/pop",
    "gpm": "NASA/GPM_L3/IMERG_MONTHLY_V07",
    "chirps": "UCSB-CHG/CHIRPS/DAILY",
    "esa_worldcover": "ESA/WorldCover/v100",
    "hydrosheds": "WWF/HydroSHEDS/03VFDEM",
    "flood_gfsm": "projects/floodsus/assets/fsm_ei5",
    "landslide_ilsm": "projects/ee-nirdeshsharmanith1/assets/ILSM_probability",
    "coastline": "NGDC/OSD",
    "imd_rainfall": "IMD/GRIDALL/MRC_DAILY",
}

FOOTPRINTS = {
    "uttarakhand": {
        "bbox": (79.07, 29.91, 80.12, 31.09),
        "state": "Uttarakhand",
        "hazards": ["landslide", "cloudburst", "flood"],
        "scale": 60,
    },
    "odisha": {
        "bbox": (86.23, 20.28, 87.08, 20.82),
        "state": "Odisha",
        "hazards": ["flood", "coastal_erosion", "cloudburst"],
        "scale": 60,
    },
    "maharashtra": {
        "bbox": (73.00, 17.50, 81.00, 22.00),
        "state": "Maharashtra",
        "hazards": ["flood", "coastal_erosion", "landslide", "cloudburst"],
        "scale": 60,
    },
}


def _key(state):
    return (state or "").strip().lower().replace(" ", "_")


def footprint_for_state(state):
    """Case-insensitive lookup of a state footprint.

    Falls back to the state boundary GeoJSON (if configured) or to
    Uttarakhand's footprint when the state is unknown.
    """
    key = _key(state)
    if key in FOOTPRINTS:
        return FOOTPRINTS[key]
    for k, fp in FOOTPRINTS.items():
        if _key(fp.get("state")) == key:
            return fp
    boundary = os.getenv("STATE_BOUNDARY_GEOJSON")
    if boundary and Path(boundary).exists():
        gdf = gpd.read_file(boundary)
        name_col = "ST_NM" if "ST_NM" in gdf.columns else gdf.columns[0]
        match = gdf[gdf[name_col].astype(str).str.strip().str.lower() == key]
        if not match.empty:
            bounds = match.total_bounds
            return {
                "bbox": tuple(bounds),
                "state": match.iloc[0][name_col],
                "hazards": [],
                "scale": 30,
            }
    print(f"  Warning: no footprint for '{state}', defaulting to Uttarakhand")
    return FOOTPRINTS["uttarakhand"]


COLLECTIONS = {
    "UCSB-CHG/CHIRPS/DAILY",
    "projects/floodsus/assets/fsm_ei5",
}

HAZARD_WEIGHTS = {
    "flood": 0.35,
    "landslide": 0.30,
    "coastal": 0.20,
    "cloudburst": 0.15,
}

RED_ZONE_THRESHOLDS = [0.25, 0.50, 0.75]
CATEGORY_NAMES = ["Low", "Moderate", "High", "Very High"]
RED_ZONE_RULE = {"Very High": "RED", "High": "ORANGE", "Moderate": "YELLOW", "Low": "GREEN"}

CB_NORM = {"dem": 2500.0, "slope": 45.0, "drainage": 1.0, "twi": 25.0, "extreme_rain": 5.0}
CB_WEIGHTS = {"dem": 0.20, "slope": 0.25, "drainage": 0.20, "twi": 0.15, "extreme_rain": 0.20}

FLOOD_NORM = {"gfsm_class": 5.0}
LANDSLIDE_NORM = {"ilsm_prob": 1.0}
COASTAL_HARD_RISK_M = 250.0
COASTAL_EROSION_BAND_M = 3000.0

OUTPUT_DIR = BASE_DIR / "data" / "gee_output"
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

EXPORT_SCALE = 60
EXPORT_MAX_PIXELS = 1e8

VOLUME_EXPORT_BATCH_SIZE = 5

ASSET_PREFIX = "projects/tejas-470510/assets/sih"
