import numpy as np

from .base import clamp01, zonal_mean


def landslide_score(villages, raster_path, source_crs=None):
    out = villages.copy()
    scores = []
    for g in out.geometry:
        v = zonal_mean(raster_path, g, source_crs)
        scores.append(clamp01(v) if np.isfinite(v) else np.nan)
    out["landslide_score"] = scores
    return out