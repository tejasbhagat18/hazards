import numpy as np
import rasterio
import geopandas as gpd
from rasterio.transform import from_origin
from shapely.geometry import LineString, Polygon

from backend.config.settings import SAMPLE_DIR, HAZARD_RASTER_MAP, VILLAGES_FILE, DISTRICT

LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = DISTRICT["bbox"]
CELL = 0.003
N_ROWS = max(10, int(round((LAT_MAX - LAT_MIN) / CELL)))
N_COLS = max(10, int(round((LON_MAX - LON_MIN) / CELL)))
RNG = np.random.default_rng(42)
N_VILLAGES = 150


def _smooth(a, iters=8):
    x = a.astype(float)
    k = np.array([0.25, 0.5, 0.25])
    for _ in range(iters):
        x = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), axis=1, arr=x)
        x = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), axis=0, arr=x)
    return x


def _field(low, high):
    f = _smooth(RNG.uniform(0, 1, (N_ROWS, N_COLS)))
    span = f.max() - f.min()
    return low + (high - low) * (f - f.min()) / (span + 1e-9)


def _write_tif(path, arr):
    with rasterio.open(
        path, "w", driver="GTiff", height=N_ROWS, width=N_COLS,
        count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(LON_MIN, LAT_MAX, CELL, CELL),
    ) as dst:
        dst.write(arr.astype("float32"), 1)


def _build_rasters():
    gfsm = RNG.integers(1, 6, (N_ROWS, N_COLS)).astype(float)
    _write_tif(HAZARD_RASTER_MAP["flood"], gfsm)
    _write_tif(HAZARD_RASTER_MAP["landslide"], _field(0.0, 1.0))
    _write_tif(HAZARD_RASTER_MAP["twi"], _field(4.0, 24.0))
    _write_tif(HAZARD_RASTER_MAP["drainage"], _field(0.0, 1.0))
    _write_tif(HAZARD_RASTER_MAP["extreme_rain"], _field(0.0, 6.0))
    lat_slope = np.linspace(300.0, 2900.0, N_ROWS)[:, None]
    elev = lat_slope + RNG.normal(0, 60, (N_ROWS, N_COLS))
    _write_tif(HAZARD_RASTER_MAP["dem"], elev)
    grad = np.abs(np.gradient(elev, CELL)[0])
    _write_tif(HAZARD_RASTER_MAP["slope"], _field(0.0, 40.0) + grad * 3.0)

    cols = np.arange(N_COLS) * CELL + LON_MIN
    dist_arr = np.abs(cols[None, :] - (LON_MAX - 0.05))
    _write_tif(HAZARD_RASTER_MAP["coastal_distance"], dist_arr)


def _build_vectors():
    lp, rp = np.array([LON_MIN + 0.01, LAT_MIN + 0.01]), np.array([LON_MAX - 0.01, LAT_MAX - 0.01])
    geom = []
    for i in range(N_VILLAGES):
        c = RNG.uniform(lp, rp)
        b = RNG.uniform(0.0003, 0.0006)
        geom.append(Polygon([c, (c[0] + b, c[1]), (c[0] + b, c[1] + b), (c[0], c[1] + b)]).buffer(0.0))
    gdf = gpd.GeoDataFrame(
        {"village_id": [f"V-{i+1:03d}" for i in range(N_VILLAGES)],
         "name": [f"Sample Village {i+1}" for i in range(N_VILLAGES)],
         "district": [DISTRICT["state"]] * N_VILLAGES,
         "geometry": geom},
        crs="EPSG:4326",
    )
    gdf.to_file(VILLAGES_FILE, driver="GeoJSON")
    coast = gpd.GeoDataFrame(
        {"geometry": [LineString([(LON_MIN, LAT_MIN + 0.02), (LON_MAX, LAT_MIN + 0.02)])]},
        crs="EPSG:4326",
    )
    coast.to_file(SAMPLE_DIR / "coastline.geojson", driver="GeoJSON")


def ensure_sample(force=False):
    from backend.config.settings import SAMPLE_COASTLINE_FILE

    need = force or not HAZARD_RASTER_MAP["drainage"].exists() or not VILLAGES_FILE.exists()
    if need:
        _build_rasters()
        _build_vectors()
        print(f"Sample data written to {SAMPLE_DIR}")

    if not SAMPLE_COASTLINE_FILE.exists():
        gpd.GeoDataFrame(
            {"geometry": [LineString([(LON_MIN, LAT_MIN + 0.02), (LON_MAX, LAT_MIN + 0.02)])]},
            crs="EPSG:4326",
        ).to_file(SAMPLE_COASTLINE_FILE, driver="GeoJSON")


if __name__ == "__main__":
    ensure_sample(force=True)