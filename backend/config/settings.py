import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"
OUTPUT_DIR = DATA_DIR / "output"
GEE_OUTPUT_DIR = DATA_DIR / "gee_output"
GEE_ASSET_PREFIX = os.getenv("GEE_ASSET_PREFIX", "projects/tejas-470510/assets/sih")

for d in (DATA_DIR, RAW_DIR, PROCESSED_DIR, SAMPLE_DIR, OUTPUT_DIR, GEE_OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

GEE_PROJECT = os.getenv("GEE_PROJECT", "tejas-470510")
GEE_CREDENTIALS = os.getenv("GEE_CREDENTIALS", None)
USE_GEE = os.getenv("USE_GEE", "false").lower() == "true"

DISTRICTS = {
    "chamoli": {"bbox": (79.07, 29.91, 80.12, 31.09), "state": "Uttarakhand", "type": "hill"},
    "kendrapara": {"bbox": (86.23, 20.28, 87.08, 20.82), "state": "Odisha", "type": "coastal"},
}
ACTIVE_DISTRICT = os.getenv("SIH_DISTRICT", "chamoli")
DISTRICT = DISTRICTS[ACTIVE_DISTRICT]

HAZARD_RASTER_MAP = {
    "flood": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_flood_gfsm_like.tif",
    "landslide": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_landslide_ilsm_like.tif",
    "dem": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_dem.tif",
    "slope": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_slope.tif",
    "drainage": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_drainage.tif",
    "twi": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_twi.tif",
    "extreme_rain": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_extreme_rain.tif",
    "coastal_distance": SAMPLE_DIR / f"{ACTIVE_DISTRICT}_coastal_distance.tif",
}

VILLAGES_FILE = SAMPLE_DIR / f"{ACTIVE_DISTRICT}_villages.geojson"
EXT_VILLAGES_FILE = os.getenv("VILLAGES_FILE")
PROCESSED_VILLAGES_FILE = PROCESSED_DIR / f"village_boundaries_{ACTIVE_DISTRICT}.geojson"
SAMPLE_COASTLINE_FILE = SAMPLE_DIR / "coastline.geojson"
RAW_COASTLINE_FILE = RAW_DIR / "coastline.geojson"
OUTPUT_FILE = PROCESSED_DIR / f"village_risk_{ACTIVE_DISTRICT}.csv"

RAW_RASTER_MAP = {
    "flood": RAW_DIR / f"flood_{ACTIVE_DISTRICT}.tif",
    "landslide": RAW_DIR / f"ilsm_{ACTIVE_DISTRICT}.tif",
    "dem": RAW_DIR / f"dem_{ACTIVE_DISTRICT}.tif",
    "slope": RAW_DIR / f"slope_{ACTIVE_DISTRICT}.tif",
    "drainage": RAW_DIR / f"drainage_{ACTIVE_DISTRICT}.tif",
    "twi": RAW_DIR / f"twi_{ACTIVE_DISTRICT}.tif",
    "extreme_rain": RAW_DIR / f"extreme_rain_{ACTIVE_DISTRICT}.tif",
    "coastal_distance": RAW_DIR / f"coastal_distance_{ACTIVE_DISTRICT}.tif",
}


def pick(raster_key):
    raw = RAW_RASTER_MAP.get(raster_key)
    if raw and raw.exists():
        return raw
    return HAZARD_RASTER_MAP[raster_key]


def coastline_file():
    if RAW_COASTLINE_FILE.exists():
        return RAW_COASTLINE_FILE
    return SAMPLE_COASTLINE_FILE