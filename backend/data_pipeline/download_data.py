import argparse
import math
import os
import shutil
import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import rasterio
from rasterio.merge import merge as rio_merge

from backend.config import settings
from backend.config.settings import RAW_DIR

GFSM_ASSET = os.getenv("GEE_ASSET_FLOOD_GFSM", "") or None
ILSM_ASSET = os.getenv("GEE_ASSET_LANDSLIDE_ILSM", "") or None
COAST_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_coastline.geojson"
DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif"

CHUNK = 1 << 20


def _download(url, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"exists: {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "sih-geo/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            while True:
                b = r.read(CHUNK)
                if not b:
                    break
                f.write(b)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"skip missing tile: {url}")
            return None
        raise
    print(f"downloaded: {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def _dem_tile_name(lat_corner, lon_corner):
    lat = math.floor(lat_corner)
    lon = math.floor(lon_corner)
    return f"Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM"


def download_dem(bbox, force=False):
    lon_min, lat_min, lon_max, lat_max = bbox
    tiles = []
    for lat in range(math.floor(lat_min), math.ceil(lat_max) + 1):
        for lon in range(math.floor(lon_min), math.ceil(lon_max) + 1):
            tile = _dem_tile_name(lat if lat > 0 else 0, lon)
            tiles.append((tile, _download(DEM_URL.format(tile=tile), RAW_DIR / f"dem_{lat}_{lon}.tif", ) if not force else None))
    return tiles


def merge_dem(bbox, tiles, name):
    srcs = [rasterio.open(str(t[1])) for t in tiles if t[1] and t[1].exists()]
    if not srcs:
        print("no dem tiles found")
        return
    merged, transform = rio_merge(srcs, bounds=bbox, nodata=-32767)
    dst = RAW_DIR / f"dem_{name}.tif"
    with rasterio.open(str(dst), "w", driver="GTiff", height=merged.shape[1], width=merged.shape[2],
                       count=1, dtype=merged.dtype, crs="EPSG:4326", transform=transform) as out:
        out.write(merged[0], 1)
    for s in srcs:
        s.close()
    print(f"merged dem: {dst}")
    with rasterio.open(str(dst)) as d:
        arr = d.read(1)
        dx = d.transform[0]
        gx, gy = np.gradient(arr, dx)
        slope = (np.degrees(np.arctan(np.sqrt(gx * gx + gy * gy)))).astype(np.float32)
    slope_dst = RAW_DIR / f"slope_{name}.tif"
    with rasterio.open(str(slope_dst), "w", driver="GTiff", height=slope.shape[0], width=slope.shape[1],
                       count=1, dtype="float32", crs="EPSG:4326", transform=transform) as out:
        out.write(slope, 1)
    print(f"slope written: {slope_dst}")


def download_coast():
    return _download(COAST_URL, RAW_DIR / "coastline.geojson")


def download_gee(bbox, scale=30, project=None, district="raw"):
    try:
        import ee
    except ImportError as e:
        print("pip install earthengine-api  then:  python -m venv/env run `earthengine authenticate` once")
        raise SystemExit(1)
    try:
        ee.Initialize()
    except Exception:
        if not project:
            print("Earth Engine needs a project id. Find it at code.earthengine.google.com, then either:\n"
                  "  earthengine set_project PROJECT_ID       (one time)\n"
                  "  or rerun with: --project PROJECT_ID")
            raise SystemExit(2)
        ee.Initialize(project=project)
    project = project or os.environ.get("GEE_PROJECT")
    region = ee.Geometry.Rectangle(list(bbox))
    for layer, asset, res in [("flood", GFSM_ASSET, scale), ("landslide", ILSM_ASSET, 100)]:
        if not asset:
            env_name = "GEE_ASSET_FLOOD_GFSM" if layer == "flood" else "GEE_ASSET_LANDSLIDE_ILSM"
            print(f"skip {layer}: set {env_name} to the Earth Engine asset id")
            continue
        if layer == "flood":
            img = ee.ImageCollection(asset).filterBounds(region).mosaic().select(0)
            img = img.updateMask(img.gte(1).And(img.lte(5))).unmask(0).toByte()
        else:
            img = ee.Image(asset)
        url = img.getDownloadURL({"region": region, "scale": res, "crs": "EPSG:4326", "format": "GEO_TIFF"})
        req = urllib.request.Request(url, headers={"User-Agent": "sih-geo/1.0"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
        key = "flood" if layer == "flood" else "ilsm"
        dest = RAW_DIR / f"{key}_{district}.tif"
        if data[:2] in (b"II", b"MM"):
            with open(dest, "wb") as f:
                f.write(data)
        else:
            zf = zipfile.ZipFile(BytesIO(data))
            tifs = [n for n in zf.namelist() if n.lower().endswith(".tif")]
            if not tifs:
                print(f"no tif returned for {layer}")
                continue
            with open(dest, "wb") as f:
                f.write(zf.read(tifs[0]))
        print(f"saved {dest}")
    return True


def run(args):
    bbox = [float(x) for x in args.bbox.split(",")] if args.bbox else None
    district = args.name or settings.ACTIVE_DISTRICT
    if args.cmd == "dem":
        tiles = download_dem(bbox, force=args.force)
        merge_dem(bbox, tiles, district)
    elif args.cmd == "coast":
        download_coast()
    elif args.cmd == "gee":
        download_gee(bbox, scale=args.scale, project=args.project, district=district)
    else:
        print("unknown command")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["dem", "coast", "gee"])
    p.add_argument("--bbox", help="lon_min,lat_min,lon_max,lat_max")
    p.add_argument("--scale", type=int, default=30)
    p.add_argument("--project", help="Earth Engine project id (free)")
    p.add_argument("--name", help="district name used in output file names")
    p.add_argument("--force", action="store_true")
    run(p.parse_args())