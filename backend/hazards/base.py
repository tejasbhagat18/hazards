import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.warp import transform_geom


def zonal_mean(raster_path, geometry, source_crs=None):
    with rasterio.open(raster_path) as src:
        geoms = [transform_geom(source_crs or src.crs, src.crs, geometry)]
        arr, _ = rio_mask(src, geoms, crop=True, all_touched=True, nodata=src.nodata)
        band = arr[0]
        if src.nodata is not None:
            band = band[band != src.nodata]
        band = band[np.isfinite(band)]
        return float(np.mean(band)) if band.size else float("nan")


def clamp01(v):
    return max(0.0, min(1.0, float(v)))