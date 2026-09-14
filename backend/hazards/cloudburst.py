import numpy as np

from .base import clamp01, zonal_mean

NORM = {"dem": 2500.0, "slope": 45.0, "drainage": 1.0, "twi": 25.0, "extreme_rain": 5.0}
WEIGHTS = {"dem": 0.20, "slope": 0.25, "drainage": 0.20, "twi": 0.15, "extreme_rain": 0.20}


def cloudburst_score(villages, rasters, source_crs=None):
    out = villages.copy()
    raw = {k: [] for k in WEIGHTS}
    for g in out.geometry:
        for k in WEIGHTS:
            v = zonal_mean(rasters[k], g, source_crs)
            raw[k].append(clamp01(v / NORM[k]) if np.isfinite(v) else np.nan)
    for k in WEIGHTS:
        out[k] = raw[k]
    out["cloudburst_score"] = sum(WEIGHTS[k] * out[k] for k in WEIGHTS)
    return out