import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd

from backend.config import settings
from backend.hazards.flood import flood_score
from backend.hazards.landslide import landslide_score
from backend.hazards.coastal import coastal_score
from backend.hazards.cloudburst import cloudburst_score
from backend.fusion.red_zone import apply_fusion
from backend.sample_data.generate_sample_data import ensure_sample

USE_GEE = os.getenv("USE_GEE", "false").lower() == "true"


def run(use_gee=False):
    ensure_sample()
    if use_gee:
        from backend.gee.pipeline import GeeHazardPipeline
        state = settings.ACTIVE_DISTRICT.capitalize()
        if state == "Chamoli":
            state = "Uttarakhand"
        elif state == "Kendrapara":
            state = "Odisha"
        pipeline = GeeHazardPipeline(state=state, district=settings.ACTIVE_DISTRICT)
        result = pipeline.run_all()
        print(f"GEE pipeline complete for {state}")
        return result
    villages = gpd.read_file(settings.VILLAGES_FILE)
    r = flood_score(villages, settings.pick("flood"))
    r = landslide_score(r, settings.pick("landslide"))
    r = coastal_score(r, gpd.read_file(settings.coastline_file()))
    r = cloudburst_score(r, {k: settings.pick(k) for k in ("dem", "slope", "drainage", "twi", "extreme_rain")})
    r = apply_fusion(r)
    r.drop(columns=["geometry"]).to_csv(settings.OUTPUT_FILE, index=False)
    print(f"Output saved: {settings.OUTPUT_FILE}")
    print(r["red_zone_status"].value_counts().to_string())
    print(r.groupby("risk_category")["multi_hazard"].mean().round(3).to_string())
    return r


if __name__ == "__main__":
    run(use_gee=USE_GEE)
