#!/usr/bin/env python
"""Earth Engine Module 1 Pipeline Runner.

Usage:
    python backend/gee/run_gee.py --state Uttarakhand --district chamoli
    python backend/gee/run_gee.py --state Odisha --district kendrapara
    python backend/gee/run_gee.py --all-states
    python backend/gee/run_gee.py --state Maharashtra --district pune --force

Environment:
    GEE_PROJECT   - Earth Engine project ID (default: tejas-470510)
    GEE_CREDENTIALS - Path to service account JSON (optional)
"""

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from backend.gee.config import GEE_PROJECT, FOOTPRINTS, ASSET_PREFIX, EXPORT_SCALE
from backend.gee.pipeline import GeeHazardPipeline


def parse_args():
    p = argparse.ArgumentParser(
        description="SIH 2026 Module 1: Earth Engine Hazard Intelligence Pipeline"
    )
    p.add_argument("--state", help="Target state (Uttarakhand/Odisha/Maharashtra)")
    p.add_argument("--district", help="District identifier")
    p.add_argument("--all-states", action="store_true",
                   help="Run all demo states (Uttarakhand + Odisha)")
    p.add_argument("--force", action="store_true",
                   help="Force re-download of all GEE assets")
    p.add_argument("--project", default=GEE_PROJECT,
                   help=f"GEE project ID (default: {GEE_PROJECT})")
    p.add_argument("--credentials", default=None,
                   help="Path to GEE service account JSON")
    p.add_argument("--export-assets", action="store_true",
                   help="Export hazard rasters as GEE assets")
    return p.parse_args()


def init_ee(project, credentials):
    if credentials and os.path.exists(credentials):
        ee.Initialize(credentials=credentials)
    else:
        try:
            ee.Initialize(project=project)
        except Exception:
            ee.Authenticate()
            ee.Initialize(project=project)
    print(f"Earth Engine initialized with project: {project}")


def run_state(state, district, force, export_assets=False):
    if district is None:
        district = state.lower().replace(" ", "_")
    pipeline = GeeHazardPipeline(state=state, district=district, force=force)
    result = pipeline.run_all()
    if export_assets:
        _export_assets(pipeline, state, district)
    return result


def _export_assets(pipeline, state, district):
    print(f"\nExporting hazard rasters as GEE assets for {state}...")
    asset_id = f"{ASSET_PREFIX}/{state.lower()}_{district}"
    for col in ["flood_score", "landslide_score", "cloudburst_score",
                 "coastal_erosion_score", "multi_hazard"]:
        raster_path = pipeline.rasters.get(col)
        if raster_path is not None:
            print(f"  Asset export would be: {asset_id}_{col}")
    print(f"  All assets would be at: {asset_id}")


def main():
    args = parse_args()
    init_ee(args.project, args.credentials)
    states = []
    if args.all_states:
        states = ["Uttarakhand", "Odisha"]
        if args.state:
            states.append(args.state)
    elif args.state:
        states = [args.state]
    else:
        states = ["Uttarakhand"]
    results = {}
    for state in states:
        if state.lower() not in [k.lower() for k in FOOTPRINTS]:
            print(f"Unknown state: {state}. Skipping.")
            continue
        try:
            result = run_state(state, args.district, args.force, args.export_assets)
            results[state] = result
            print(f"\n{'='*60}")
            print(f"COMPLETED: {state}")
            print(f"  Records: {result['records']}")
            print(f"  Red Zones: {result['red_zone_counts']}")
            print(f"  Mean Multi-Hazard: {result['mean_multi_hazard']:.4f}")
            print(f"{'='*60}")
        except Exception as e:
            print(f"ERROR processing {state}: {e}")
            import traceback
            traceback.print_exc()
    print(f"\n{'#'*60}")
    print(f"PIPELINE COMPLETE. Processed {len(results)} state(s).")
    print(f"{'#'*60}")


if __name__ == "__main__":
    main()
