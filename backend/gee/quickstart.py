#!/usr/bin/env python
"""Quick start script for SIH 2026 Module 1: Earth Engine Pipeline.

Usage:
    python backend/gee/quickstart.py --state Uttarakhand
    python backend/gee/quickstart.py --all-states
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("GEE_PROJECT", "tejas-470510")
os.environ["USE_GEE"] = "true"

import ee
from backend.gee.config import GEE_PROJECT, FOOTPRINTS
from backend.gee.pipeline import GeeHazardPipeline


def quickstart(state="Uttarakhand", district=None, force=False):
    print("=" * 60)
    print("SIH 2026 Module 1: Quick Start")
    print(f"State: {state} | GEE Project: {GEE_PROJECT}")
    print("=" * 60)

    print("\nInitializing Earth Engine...")
    ee.Initialize(project=GEE_PROJECT)
    print("  OK")

    if district is None:
        district = state.lower().replace(" ", "_")

    pipeline = GeeHazardPipeline(state=state, district=district, force=force)
    result = pipeline.run_all()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  Total villages: {result['records']}")
    print(f"  Red Zones: {result['red_zone_counts']}")
    print(f"  Mean Multi-Hazard Score: {result['mean_multi_hazard']:.4f}")
    print(f"\n  Output files:")
    print(f"    CSV: {result['csv']}")
    print(f"    GeoJSON: {result['geojson']}")

    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--state", default="Uttarakhand")
    p.add_argument("--district", default=None)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    quickstart(args.state, args.district, args.force)