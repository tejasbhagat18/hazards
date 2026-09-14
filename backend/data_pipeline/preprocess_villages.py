"""Preprocess any survey-of-india village shapefile into pipeline-ready GeoJSON.

Usage (easy, interactive):
    python -m backend.data_pipeline.preprocess_villages --state UTTARAKHAND --district CHAMOLI

Usage (defaults = the 2 demo districts):
    python -m backend.data_pipeline.preprocess_villages

Description:
  Reads a state .shp from the indian_village_boundries folder, filters to ONE
  district, renames columns to the pipeline's expected names
  (village_id / name / district), reprojects LCC_WGS84 -> EPSG:4326 and writes
  GeoJSON to backend/data/processed/village_boundaries_<district>.geojson.

  To add a NEW state later:
    1) Put the state's shapefile in Downloads/indian_village_boundries (already there)
    2) Run this script with --state <SHP_NAME_WITHOUT_EXT> --district <DISTRICT>
    3) Follow docs/ADD_A_NEW_STATE.md to export the GEE rasters and run the pipeline
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd

from backend.config.settings import PROCESSED_DIR

VILLAGE_SHP_DIR = Path(os.getenv("VILLAGE_SHP_DIR", str(Path.home() / "Downloads" / "indian_village_boundries")))

# Defaults for the two demo districts (used when no CLI args given)
DEFAULTS = [
    {"shp": "UTTARAKHAND.shp", "district": "CHAMOLI", "state": "Uttarakhand"},
    {"shp": "ODISHA.shp", "district": "KENDRAPARA", "state": "Odisha"},
]

FIELD_MAP = {
    "Vill_LGD": "village_id",
    "Vill_name": "name",
    "District": "district",
}


def district_slug(value):
    """Portable file/API key for district names such as NORTH EAST."""
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def preprocess(shp_name, district_upper, state_name, out_dir=PROCESSED_DIR):
    shp_path = VILLAGE_SHP_DIR / shp_name
    if not shp_path.exists():
        raise FileNotFoundError(f"Shapefile not found: {shp_path}")
    district_key = district_slug(district_upper)

    print(f"[{district_key}] Reading {shp_path.name}...")
    gdf = gpd.read_file(shp_path)
    total = len(gdf)

    district_col = "District" if "District" in gdf.columns else None
    if district_col is None:
        for c in gdf.columns:
            if "dist" in c.lower():
                district_col = c
                break
    if district_col is None:
        raise ValueError("No district column found in shapefile")

    match = gdf[gdf[district_col].astype(str).str.strip().str.upper() == district_upper]
    if match.empty:
        avail = sorted(gdf[district_col].astype(str).str.strip().str.upper().unique())[:25]
        raise ValueError(f"No district '{district_upper}' in {shp_name}. Available: {avail}")
    gdf = match.copy()
    print(f"[{district_key}] Filtered {total} -> {len(gdf)} villages ({district_upper})")

    # OBJECTID is retained only long enough to create a stable fallback where
    # urban units have no official village LGD code.
    keep = [c for c in FIELD_MAP if c in gdf.columns] + [c for c in ["OBJECTID"] if c in gdf.columns] + ["geometry"]
    gdf = gdf[keep].rename(columns=FIELD_MAP)
    if "village_id" not in gdf.columns:
        gdf["village_id"] = None
    fallback = gdf["OBJECTID"].astype(str) if "OBJECTID" in gdf.columns else gdf.index.astype(str)
    valid_id = gdf["village_id"].notna() & gdf["village_id"].astype(str).str.strip().ne("")
    gdf["village_id"] = gdf["village_id"].where(valid_id, "UNIT-" + district_key + "-" + fallback)
    gdf["village_id"] = gdf["village_id"].astype(str)
    # Some urban source records reuse an LGD value for multiple mapped units.
    # Preserve the LGD where unique; append the stable source ID only when needed.
    duplicate_id = gdf["village_id"].duplicated(keep=False)
    gdf.loc[duplicate_id, "village_id"] = (
        gdf.loc[duplicate_id, "village_id"] + "-UNIT-" + fallback.loc[duplicate_id]
    )
    if "name" not in gdf.columns:
        gdf["name"] = None
    gdf["name"] = gdf["name"].where(gdf["name"].notna(), "Mapped unit " + gdf["village_id"])
    gdf = gdf.drop(columns=["OBJECTID"], errors="ignore")
    gdf["state"] = state_name

    gdf = gdf.to_crs("EPSG:4326")
    out = out_dir / f"village_boundaries_{district_key}.geojson"
    gdf.to_file(out, driver="GeoJSON")
    print(f"[{district_key}] Saved: {out}  (CRS EPSG:4326, bounds {[round(x, 3) for x in gdf.total_bounds]})")
    return gdf


def main():
    p = argparse.ArgumentParser(description="Preprocess a village shapefile -> GeoJSON")
    p.add_argument("--state", help="Shapefile name without .shp, e.g. UTTARAKHAND")
    p.add_argument("--district", help="District name (uppercase), e.g. CHAMOLI")
    p.add_argument("--state-name", help="Display name, e.g. Uttarakhand (defaults to state arg)")
    p.add_argument("--all-districts", action="store_true", help="Preprocess every district in the state shapefile")
    args = p.parse_args()

    jobs = []
    if args.state and args.all_districts:
        state_path = VILLAGE_SHP_DIR / f"{args.state}.shp"
        source = gpd.read_file(state_path)
        district_col = "District" if "District" in source.columns else next((c for c in source.columns if "dist" in c.lower()), None)
        if district_col is None:
            raise ValueError("No district column found in shapefile")
        jobs = [{"shp": args.state + ".shp", "district": d, "state": args.state_name or args.state.title()}
                for d in sorted(source[district_col].dropna().astype(str).str.strip().str.upper().unique())]
    elif args.state and args.district:
        jobs = [{"shp": args.state + ".shp", "district": args.district,
                 "state": args.state_name or args.district.title()}]
    else:
        jobs = DEFAULTS

    for job in jobs:
        try:
            preprocess(job["shp"], job["district"], job["state"])
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    print("Done.")


if __name__ == "__main__":
    main()
