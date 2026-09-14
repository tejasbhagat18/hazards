#!/usr/bin/env python
"""Register SIH 2026 hazard assets in Google Earth Engine.

This script creates GEE ImageAssets from locally downloaded rasters
and registers them in the project for sharing and dashboard access.

Usage:
    python backend/gee/register_assets.py --state Uttarakhand --district chamoli
    python backend/gee/register_assets.py --all-states
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from backend.gee.config import GEE_PROJECT, ASSET_PREFIX
from backend.config.settings import RAW_DIR


def init_ee():
    try:
        ee.Initialize(project=GEE_PROJECT)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=GEE_PROJECT)


def _get_asset_id(state, district, layer):
    return f"{ASSET_PREFIX}/{state.lower()}_{district}_{layer}"


def register_raster(state, district, layer, raster_path):
    asset_id = _get_asset_id(state, district, layer)
    try:
        existing = ee.Image(asset_id).getInfo()
        print(f"  Asset exists: {asset_id}")
        return asset_id
    except Exception:
        pass
    if not Path(raster_path).exists():
        print(f"  File not found: {raster_path}")
        return None
    task = ee.batch.Export.image.toAsset(
        image=ee.Image(raster_path),
        description=f"register_{state}_{district}_{layer}",
        assetId=asset_id,
        pyramidingPolicy={"*.default": "mode"},
        scale=30,
        maxPixels=1e13,
    )
    task.start()
    print(f"  Export started: {asset_id}")
    return asset_id


def register_all_assets(state, district):
    init_ee()
    raw_dir = RAW_DIR
    layers = [
        ("dem", f"dem_{district}.tif"),
        ("slope", f"slope_{district}.tif"),
        ("flood", f"flood_{district}.tif"),
        ("landslide", f"landslide_{district}.tif"),
        ("cloudburst", f"cloudburst_{district}.tif"),
    ]
    registered = []
    for layer, filename in layers:
        path = raw_dir / filename
        if path.exists():
            aid = register_raster(state, district, layer, str(path))
            if aid:
                registered.append(aid)
    return registered


def main():
    p = argparse.ArgumentParser(description="Register GEE assets for SIH 2026")
    p.add_argument("--state", help="State name")
    p.add_argument("--district", help="District identifier")
    p.add_argument("--all-states", action="store_true")
    args = p.parse_args()

    init_ee()
    states = []
    if args.all_states:
        states = ["Uttarakhand", "Odisha"]
    elif args.state:
        states = [args.state]
    else:
        states = ["Uttarakhand"]

    for state in states:
        district = args.district or state.lower()
        print(f"\nRegistering assets for {state} ({district})...")
        registered = register_all_assets(state, district)
        print(f"  Registered {len(registered)} assets")

    print("\nAll assets registered.")
    print(f"\nAsset prefix: {ASSET_PREFIX}")
    print("Use these in the dashboard for visualization.")


if __name__ == "__main__":
    main()
