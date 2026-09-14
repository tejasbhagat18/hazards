import numpy as np

HARD_RISK_M = 250.0
EROSION_BAND_M = 3000.0


def coastal_score(villages, coastline, hard_risk_m=HARD_RISK_M, erosion_band_m=EROSION_BAND_M):
    out = villages.copy()
    coast = coastline.to_crs(epsg=3857).geometry.unary_union
    proj = out.to_crs(epsg=3857)
    dists = [g.centroid.distance(coast) for g in proj.geometry]

    def to_score(dist):
        if dist <= hard_risk_m:
            return 1.0
        return float(max(0.0, 1.0 - (dist - hard_risk_m) / (erosion_band_m - hard_risk_m)))

    out["coast_dist_m"] = dists
    out["coastal_erosion_score"] = [to_score(d) for d in dists]
    return out