import numpy as np

from .base import clamp01, zonal_mean


def flood_score(villages, raster_path, source_crs=None):
    out = villages.copy()
    scores = []
    for g in out.geometry:
        v = zonal_mean(raster_path, g, source_crs)
        if np.isfinite(v):
            scores.append(clamp01((v - 1) / 4))
        else:
            scores.append(np.nan)
    out["flood_score"] = scores
    return out