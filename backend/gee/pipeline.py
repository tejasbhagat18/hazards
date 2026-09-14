import ee
import json
import zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from io import BytesIO
from rasterio.transform import from_origin
from rasterio.merge import merge as rio_merge
from rasterio.warp import reproject, Resampling
from pathlib import Path
from shapely.geometry import Polygon, box
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.gee.config import (
    GEE_PROJECT, ASSETS, FOOTPRINTS, HAZARD_WEIGHTS,
    RED_ZONE_THRESHOLDS, CATEGORY_NAMES, RED_ZONE_RULE,
    CB_NORM, CB_WEIGHTS, FLOOD_NORM, LANDSLIDE_NORM,
    COASTAL_HARD_RISK_M, COASTAL_EROSION_BAND_M,
    OUTPUT_DIR, RAW_DIR, PROCESSED_DIR,
    EXPORT_SCALE, EXPORT_MAX_PIXELS, ASSET_PREFIX,
    COLLECTIONS, footprint_for_state,
)
from backend.config.settings import DISTRICTS, ACTIVE_DISTRICT
from backend.fusion.red_zone import apply_fusion


class GeeHazardPipeline:
    """Earth Engine pipeline for Module 1: Hazard Intelligence.

    Produces per-village hazard scores and Red Zone classification
    using GEE geospatial assets for flood, landslide, coastal
    erosion, and cloudburst hazards.
    """

    def __init__(self, state="Uttarakhand", district=None, force=False):
        self.state = state
        self.district = district or ACTIVE_DISTRICT
        self.force = force
        self.config = footprint_for_state(state, self.district)
        self.bbox = self.config["bbox"]
        self.scale = self.config.get("scale", EXPORT_SCALE)
        self.region = ee.Geometry.Rectangle(list(self.bbox))
        self.villages_gdf = None
        self.rasters = {}
        self.results = None
        ee.Initialize(project=GEE_PROJECT)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _get_collection(self, asset_id, params=None):
        """Return a single ee.Image for the given asset.

        Assets stored as ImageCollections (GPM, CHIRPS, GFSM) are mosaiced
        over the region; single images are returned as-is.
        """
        if not asset_id:
            raise ValueError(
                "A required Earth Engine asset is not configured. Set "
                "GEE_ASSET_FLOOD_GFSM / GEE_ASSET_LANDSLIDE_ILSM (see "
                "backend/config/.env.example)."
            )
        if asset_id in COLLECTIONS:
            return ee.ImageCollection(asset_id).filterBounds(self.region).mosaic()
        return ee.Image(asset_id)

    def _download_ee_image(self, img, name, scale=None):
        scale = scale or self.scale
        dest = RAW_DIR / f"{name}_{self.district}.tif"
        if dest.exists() and not self.force:
            print(f"  skip (exists): {dest}")
            return dest
        import urllib.request
        for attempt_scale in (scale, scale * 2, scale * 3, scale * 6):
            try:
                url = img.getDownloadURL({
                    "region": self.region,
                    "scale": attempt_scale,
                    "crs": "EPSG:4326",
                    "format": "GEO_TIFF",
                    "maxPixels": EXPORT_MAX_PIXELS,
                })
                req = urllib.request.Request(url, headers={"User-Agent": "sih-gee-pipeline/1.0"})
                with urllib.request.urlopen(req, timeout=600) as r:
                    data = r.read()
                if data[:2] == b"PK":
                    zf = zipfile.ZipFile(BytesIO(data))
                    tifs = [n for n in zf.namelist() if n.lower().endswith((".tif", ".tiff"))]
                    if not tifs:
                        print(f"  ERROR no tif found in archive for {name}")
                        return None
                    with open(dest, "wb") as f:
                        f.write(zf.read(tifs[0]))
                else:
                    with open(dest, "wb") as f:
                        f.write(data)
                print(f"  saved (scale {attempt_scale}m): {dest} ({len(data)/1e6:.1f} MB)")
                return dest
            except Exception as e:
                msg = str(e)
                if "must be less than or equal to" in msg or "request size" in msg.lower():
                    print(f"  download too large at {attempt_scale}m, retrying at {attempt_scale * 2}m...")
                    continue
                print(f"  ERROR downloading {name} at {attempt_scale}m: {e}")
                return None

    def _reproject_to_4326(self, src_path, dest_path, target_crs="EPSG:4326"):
        with rasterio.open(src_path) as src:
            if src.crs.to_string() == target_crs:
                return
            transform, width, height = rasterio.warp.calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds,
                resolution=src.res[0]
            )
            dst = rasterio.open(
                dest_path, "w", driver="GTiff",
                height=height, width=width, count=src.count,
                dtype="float32", crs=target_crs, transform=transform
            )
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=transform, dst_crs=target_crs,
                resampling=Resampling.bilinear,
            )
            dst.close()
            src.close()
            return dest_path

    def step1_village_layer(self, source="soi"):
        print(f"\n{'='*60}")
        print(f"STEP 1: Village Boundary Import ({self.state})")
        print(f"{'='*60}")
        if source == "soi":
            try:
                villages = self._load_soi_villages()
            except Exception as e:
                print(f"  SoI load failed ({e}), falling back to local")
                villages = self._load_local_villages()
        else:
            villages = self._load_local_villages()
        self.villages_gdf = villages
        print(f"  Loaded {len(villages)} villages for {self.state}")
        print(f"  Bounds: {list(villages.total_bounds)}")
        return villages

    def _load_soi_villages(self):
        try:
            import ee
            villages_fc = ee.FeatureCollection("users/sih/village_boundaries")
            region_fc = villages_fc.filterBounds(self.region)
            json_data = region_fc.getInfo()
            features = json_data.get("features", [])
            if not features:
                raise ValueError("No features found")
            gdf = gpd.GeoDataFrame.from_features(json_data, crs="EPSG:4326")
            gdf = gdf[gdf.intersects(self._to_shapely())]
            return gdf
        except Exception as e:
            print(f"  Note: SoI direct load failed ({e})")
            return self._load_local_villages()

    def _load_local_villages(self):
        from backend.config.settings import SAMPLE_DIR, EXT_VILLAGES_FILE, PROCESSED_DIR
        candidates = []
        if EXT_VILLAGES_FILE:
            candidates.append(Path(EXT_VILLAGES_FILE))
        candidates += [
            PROCESSED_DIR / f"village_boundaries_{self.district}.geojson",
            SAMPLE_DIR / f"{self.district}_villages.geojson",
            SAMPLE_DIR / "villages.geojson",
            Path("backend/data/sample") / f"{self.district}_villages.geojson",
        ]
        for p in candidates:
            if p.exists():
                gdf = gpd.read_file(p)
                if "district" not in gdf.columns:
                    gdf["district"] = self.config["state"]
                return gdf
        raise FileNotFoundError("No village GeoJSON found")

    def _to_shapely(self):
        return box(*self.bbox)

    def step2_dem_layer(self):
        print(f"\n{'='*60}")
        print(f"STEP 2: DEM Layer ({self.state})")
        print(f"{'='*60}")
        dem = self._get_collection(ASSETS["dem"]).clip(self.region)
        dem_path = self._download_ee_image(dem, "dem")
        if dem_path is None:
            return None
        slope = self._compute_slope(dem_path)
        dem_arr = self._raster_to_array(dem_path)
        self.rasters["dem"] = dem_arr
        self.rasters["slope"] = np.nan_to_num(slope)
        print(f"  DEM mean elevation: {np.nanmean(dem_arr):.1f} m")
        print(f"  Slope range: {np.nanmin(slope):.1f} - {np.nanmax(slope):.1f} deg")
        return dem_arr

    def _compute_slope(self, dem_path):
        from math import cos, radians
        with rasterio.open(dem_path) as src:
            arr = src.read(1).astype(float)
            dx_deg, dy_deg = src.res
            # src.res on EPSG:4326 is (lon_deg, lat_deg); convert to metres
            # using the raster's mean latitude so slope is in real degrees.
            lat_center = radians((src.bounds.top + src.bounds.bottom) / 2.0)
            m_per_deg_lon = 111320.0 * cos(lat_center)
            m_per_deg_lat = 111320.0
            gy, gx = np.gradient(arr, dy_deg * m_per_deg_lat, dx_deg * m_per_deg_lon)
            slope = np.degrees(np.arctan(np.sqrt(gx * gx + gy * gy)))
            slope[np.isnan(arr)] = np.nan
        slope_path = RAW_DIR / f"slope_{self.district}.tif"
        with rasterio.open(slope_path, "w", driver="GTiff",
                           height=slope.shape[0], width=slope.shape[1],
                           count=1, dtype="float32",
                           crs=src.crs, transform=src.transform) as out:
            out.write(slope.astype("float32"), 1)
        print(f"  Slope saved: {slope_path}")
        return slope

    def step3_rainfall_layer(self):
        print(f"\n{'='*60}")
        print(f"STEP 3: Rainfall Layer ({self.state})")
        print(f"{'='*60}")
        def _collection_mean(asset_id, band, start="2020-01-01", end="2025-12-31"):
            import ee as _ee
            return (
                _ee.ImageCollection(asset_id)
                .filterBounds(self.region)
                .filterDate(start, end)
                .select(band)
                .mean()
            )
        gpm = _collection_mean(ASSETS["gpm"], "precipitation").clip(self.region)
        gpm_path = self._download_ee_image(gpm, "gpm_rainfall")
        if gpm_path and gpm_path.exists():
            gpm_arr = self._raster_to_array(gpm_path)
            self.rasters["gpm_rainfall"] = gpm_arr
            print(f"  GPM mean rainfall: {np.nanmean(gpm_arr):.2f} mm/hr")
        else:
            gpm_arr = None
        chirps = _collection_mean(ASSETS["chirps"], "precipitation",
                                  start="2023-01-01", end="2025-12-31").clip(self.region)
        chirps_path = self._download_ee_image(chirps, "chirps_rainfall")
        if chirps_path and chirps_path.exists():
            chirps_arr = self._raster_to_array(chirps_path)
            self.rasters["chirps_rainfall"] = chirps_arr
            print(f"  CHIRPS mean rainfall: {np.nanmean(chirps_arr):.2f} mm/day")
        else:
            chirps_arr = None
        extreme_rain = None
        if gpm_arr is not None and chirps_arr is not None:
            extreme_rain = np.maximum(
                np.nan_to_num((gpm_arr - np.nanmean(gpm_arr)) / (np.nanstd(gpm_arr) + 1e-9)),
                np.nan_to_num((chirps_arr - np.nanmean(chirps_arr)) / (np.nanstd(chirps_arr) + 1e-9))
            )
            extreme_rain = np.clip(extreme_rain / 5.0, 0, 1)
            self.rasters["extreme_rain"] = extreme_rain
            print(f"  Extreme rainfall index computed")
        return self.rasters.get("extreme_rain")

    def step4_flood_risk(self):
        print(f"\n{'='*60}")
        print(f"STEP 4: Flood Risk Layer ({self.state})")
        print(f"{'='*60}")
        flood_score = None
        gfsm = self._get_collection(ASSETS["flood_gfsm"]).clip(self.region)
        gfsm_path = self._download_ee_image(gfsm, "flood_gfsm")
        if gfsm_path and gfsm_path.exists():
            with rasterio.open(gfsm_path) as src:
                gfsm_arr = src.read(1).astype(float)
            gfsm_arr = np.nan_to_num(gfsm_arr)
            flood_score = np.clip((gfsm_arr - 1) / (FLOOD_NORM["gfsm_class"] - 1), 0, 1)
            self.rasters["flood_gfsm_raw"] = gfsm_arr
            print(f"  GFSM flood score computed")
        dem = self.rasters.get("dem")
        slope = self.rasters.get("slope")
        if dem is not None and slope is not None:
            dem = np.nan_to_num(dem)
            slope = np.nan_to_num(slope)
            rain = self.rasters.get("gpm_rainfall")
            rain = np.nan_to_num(rain) if rain is not None else np.zeros_like(dem)
            if rain.shape != dem.shape:
                rain = np.zeros_like(dem)
            flood_topo = np.clip(
                (dem / 2000.0) * 0.3
                + (slope / 45.0) * 0.4
                + np.clip(rain / 10.0, 0, 1) * 0.3,
                0, 1
            )
            flood_score = flood_score if flood_score is not None else flood_topo
            flood_score = np.maximum(flood_score, flood_topo)
        if flood_score is None:
            flood_score = np.zeros_like(dem) if dem is not None else np.zeros((100, 100))
        else:
            flood_score = np.nan_to_num(flood_score)
        self.rasters["flood_score"] = flood_score
        flood_path = RAW_DIR / f"flood_{self.district}.tif"
        with rasterio.open(flood_path, "w", driver="GTiff",
                           height=flood_score.shape[0], width=flood_score.shape[1],
                           count=1, dtype="float32", crs="EPSG:4326",
                           transform=from_origin(self.bbox[0], self.bbox[3], 0.003, 0.003)) as out:
            out.write(flood_score.astype("float32"), 1)
        print(f"  Flood risk saved: {flood_path}")
        return flood_score

    def step5_landslide_risk(self):
        print(f"\n{'='*60}")
        print(f"STEP 5: Landslide Risk Layer ({self.state})")
        print(f"{'='*60}")
        landslide_score = None
        ilsm = self._get_collection(ASSETS["landslide_ilsm"]).clip(self.region)
        ilsm_path = self._download_ee_image(ilsm, "ilsm")
        if ilsm_path and ilsm_path.exists():
            with rasterio.open(ilsm_path) as src:
                ilsm_arr = src.read(1).astype(float)
            landslide_score = np.clip(np.nan_to_num(ilsm_arr) / LANDSLIDE_NORM["ilsm_prob"], 0, 1)
            self.rasters["ilsm_raw"] = ilsm_arr
            print(f"  ILSM landslide score computed")
        dem = self.rasters.get("dem")
        slope = self.rasters.get("slope")
        if dem is not None and slope is not None:
            dem = np.nan_to_num(dem)
            slope = np.nan_to_num(slope)
            rain = self.rasters.get("gpm_rainfall")
            rain = np.nan_to_num(rain) if rain is not None else np.zeros_like(dem)
            if rain.shape != dem.shape:
                rain = np.zeros_like(dem)
            ls_topo = np.clip(
                (slope / 45.0) * 0.4
                + (dem / 3000.0) * 0.2
                + np.clip(rain / 10.0, 0, 1) * 0.2
                + 0.05,
                0, 1
            )
            landslide_score = landslide_score if landslide_score is not None else ls_topo
            landslide_score = np.maximum(landslide_score, ls_topo)
        if landslide_score is None:
            slope = self.rasters.get("slope", np.zeros((100, 100)))
            landslide_score = np.clip(np.nan_to_num(slope) / 45.0, 0, 1)
        landslide_score = np.nan_to_num(landslide_score)
        self.rasters["landslide_score"] = landslide_score
        ls_path = RAW_DIR / f"landslide_{self.district}.tif"
        with rasterio.open(ls_path, "w", driver="GTiff",
                           height=landslide_score.shape[0], width=landslide_score.shape[1],
                           count=1, dtype="float32", crs="EPSG:4326",
                           transform=from_origin(self.bbox[0], self.bbox[3], 0.003, 0.003)) as out:
            out.write(landslide_score.astype("float32"), 1)
        print(f"  Landslide risk saved: {ls_path}")
        return landslide_score

    def step6_cloudburst_risk(self):
        print(f"\n{'='*60}")
        print(f"STEP 6: Cloudburst Risk Layer ({self.state})")
        print(f"{'='*60}")
        dem = self.rasters.get("dem")
        slope = self.rasters.get("slope")
        extreme_rain = self.rasters.get("extreme_rain")
        drainage = self.rasters.get("drainage")
        twi = self.rasters.get("twi")
        if dem is not None:
            if slope is None:
                slope = np.zeros_like(dem)
            if extreme_rain is None:
                extreme_rain = np.zeros_like(dem)
            if drainage is None:
                drainage = np.zeros_like(dem)
            if twi is None:
                twi = np.zeros_like(dem)
        else:
            dem = np.zeros((100, 100))
            slope = np.zeros((100, 100))
            extreme_rain = np.zeros((100, 100))
            drainage = np.zeros((100, 100))
            twi = np.zeros((100, 100))
        cb = (
            CB_WEIGHTS["dem"] * np.clip(np.nan_to_num(dem) / CB_NORM["dem"], 0, 1)
            + CB_WEIGHTS["slope"] * np.clip(np.nan_to_num(slope) / CB_NORM["slope"], 0, 1)
            + CB_WEIGHTS["drainage"] * np.clip(np.nan_to_num(drainage) / CB_NORM["drainage"], 0, 1)
            + CB_WEIGHTS["twi"] * np.clip(np.nan_to_num(twi) / CB_NORM["twi"], 0, 1)
            + CB_WEIGHTS["extreme_rain"] * np.clip(np.nan_to_num(extreme_rain) / CB_NORM["extreme_rain"], 0, 1)
        )
        cb = np.clip(cb, 0, 1)
        self.rasters["cloudburst_score"] = cb
        cb_path = RAW_DIR / f"cloudburst_{self.district}.tif"
        with rasterio.open(cb_path, "w", driver="GTiff",
                           height=cb.shape[0], width=cb.shape[1],
                           count=1, dtype="float32", crs="EPSG:4326",
                           transform=from_origin(self.bbox[0], self.bbox[3], 0.003, 0.003)) as out:
            out.write(cb.astype("float32"), 1)
        print(f"  Cloudburst risk saved: {cb_path}")
        return cb

    def step7_coastal_risk(self):
        print(f"\n{'='*60}")
        print(f"STEP 7: Coastal Erosion Risk Layer ({self.state})")
        print(f"{'='*60}")
        dem_arr = self.rasters.get("dem")
        ref = dem_arr if dem_arr is not None else np.zeros((100, 100))
        if "coastal_erosion" not in self.config.get("hazards", []):
            print(f"  {self.config['state']} is not a coastal state. Skipping.")
            # Coastal exposure is not applicable inland; exclude it from fusion
            # rather than treating it as fabricated low-risk evidence.
            self.rasters["coastal_score"] = np.full_like(ref, np.nan, dtype=float)
            return self.rasters["coastal_score"]
        try:
            coastline = ee.FeatureCollection(ASSETS.get("coastline", "NGDC/OSD")).filterBounds(self.region)
            coast_json = coastline.getInfo()
            coast_geoms = [shape(f["geometry"]) for f in coast_json.get("features", [])]
            print(f"  Loaded {len(coast_geoms)} coastline features from GEE")
        except Exception as e:
            print(f"  GEE coastline failed ({e}); falling back to local coastline.geojson")
            from backend.config.settings import RAW_COASTLINE_FILE
            coast_gdf = gpd.read_file(RAW_COASTLINE_FILE)
            coast_geoms = list(coast_gdf.geometry)
        from shapely.geometry import shape
        from shapely.ops import unary_union
        if not coast_geoms:
            print("  No coastline features in region. Skipping.")
            self.rasters["coastal_score"] = np.full_like(ref, np.nan, dtype=float)
            return np.full_like(ref, np.nan, dtype=float)
        coast_union = unary_union(coast_geoms)
        villages = self.villages_gdf
        if villages is not None:
            proj_coast = gpd.GeoSeries([coast_union], crs="EPSG:4326").to_crs(epsg=3857).iloc[0]
            proj_villages = villages.to_crs(epsg=3857)
            dists = [g.centroid.distance(proj_coast) for g in proj_villages.geometry]
            coastal_scores = [1.0 if d <= COASTAL_HARD_RISK_M else
                             float(max(0.0, 1.0 - (d - COASTAL_HARD_RISK_M) / (COASTAL_EROSION_BAND_M - COASTAL_HARD_RISK_M)))
                             for d in dists]
            self.rasters["coastal_distances_m"] = dists
            self.rasters["coastal_score"] = np.array(coastal_scores)
        else:
            self.rasters["coastal_score"] = np.full_like(ref, np.nan, dtype=float)
        print(f"  Coastal erosion computed for {self.config['state']}")
        return self.rasters["coastal_score"]

    def step8_village_aggregation(self):
        print(f"\n{'='*60}")
        print(f"STEP 8: Village-wise Hazard Aggregation ({self.state})")
        print(f"{'='*60}")
        villages = self.villages_gdf
        if villages is None:
            raise ValueError("No village layer loaded. Run step1 first.")
        flood = self.rasters.get("flood_score")
        landslide = self.rasters.get("landslide_score")
        coastal = self.rasters.get("coastal_score")
        cloudburst = self.rasters.get("cloudburst_score")
        dem_arr = self.rasters.get("dem")
        slope_arr = self.rasters.get("slope")
        if dem_arr is None:
            raise ValueError("No DEM loaded. Run step2 first.")
        records = []
        for idx, row in villages.iterrows():
            geom = row["geometry"]
            centroid = geom.centroid
            env = geom.envelope
            lon_min, lat_min, lon_max, lat_max = env.bounds
            si, sj = self._pixel_at(lon_min, lat_min, dem_arr)
            ei, ej = self._pixel_at(lon_max, lat_max, dem_arr)
            si, ei = max(0, min(si, ei)), min(dem_arr.shape[0] - 1, max(si, ei))
            sj, ej = max(0, min(sj, ej)), min(dem_arr.shape[1] - 1, max(sj, ej))
            if si >= dem_arr.shape[0] or sj >= dem_arr.shape[1]:
                si, sj = 0, 0
                ei, ej = min(1, dem_arr.shape[0] - 1), min(1, dem_arr.shape[1] - 1)
            patch = dem_arr[si:ei+1, sj:ej+1]

            def _mean(arr):
                if arr is None:
                    return np.nan
                arr = np.asarray(arr)
                if arr.ndim == 1:
                    return float(np.nanmean(arr)) if len(arr) else np.nan
                if arr.shape != dem_arr.shape:
                    return np.nan
                p = arr[si:ei+1, sj:ej+1]
                return float(np.nanmean(p)) if p.size else np.nan

            v = {
                "village_id": row.get("village_id", f"V-{idx:03d}"),
                "name": row.get("name", f"Village {idx}"),
                "district": row.get("district", self.config["state"]),
                "state": self.config["state"],
                "geometry": geom,
            }
            v["flood_score"] = _mean(flood)
            v["landslide_score"] = _mean(landslide)
            v["cloudburst_score"] = _mean(cloudburst)
            coastal_arr = np.asarray(coastal) if coastal is not None else None
            if coastal_arr is not None and coastal_arr.ndim == 1 and len(coastal_arr) == len(villages):
                v["coastal_erosion_score"] = float(coastal_arr[idx])
            else:
                v["coastal_erosion_score"] = _mean(coastal)
            v["dem"] = _mean(dem_arr)
            v["slope"] = _mean(slope_arr)
            records.append(v)
        df = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
        self.results = df
        print(f"  Aggregated {len(df)} villages")
        for col in ["flood_score", "landslide_score", "cloudburst_score", "coastal_erosion_score"]:
            if col in df.columns:
                print(f"  {col}: mean={df[col].mean():.3f}, std={df[col].std():.3f}")
        return df

    def _pixel_at(self, lon, lat, arr):
        rows, cols = arr.shape
        lon_min, lat_max = self.bbox[0], self.bbox[3]
        lon_max = self.bbox[2]
        cell_lon = (lon_max - lon_min) / cols
        cell_lat = (lat_max - self.bbox[1]) / rows
        j = int((lon - lon_min) / cell_lon)
        i = int((lat_max - lat) / cell_lat)
        return max(0, min(rows - 1, i)), max(0, min(cols - 1, j))

    def step9_red_zone_generation(self):
        print(f"\n{'='*60}")
        print(f"STEP 9: Red Zone Generation ({self.state})")
        print(f"{'='*60}")
        df = self.results
        if df is None:
            raise ValueError("No results. Run step8 first.")
        # Fusion normalizes authority-configurable weights over available
        # evidence. Missing layers lower confidence; they never become zero risk.
        df = apply_fusion(df, weights=HAZARD_WEIGHTS)
        df = df.sort_values("multi_hazard", ascending=False, na_position="last")
        self.results = df
        print(f"  Red Zone distribution:")
        print(f"    {df['red_zone_status'].value_counts().to_string()}")
        print(f"  Multi-Hazard range: {df['multi_hazard'].min():.3f} - {df['multi_hazard'].max():.3f}")
        print(f"  Confidence range: {df['risk_confidence'].min():.3f} - {df['risk_confidence'].max():.3f}")
        return df

    def step10_export(self, output_name=None):
        print(f"\n{'='*60}")
        print(f"STEP 10: Export Results ({self.state})")
        print(f"{'='*60}")
        df = self.results
        if df is None:
            raise ValueError("No results to export.")
        output_name = output_name or self.district
        csv_path = PROCESSED_DIR / f"village_risk_{output_name}.csv"
        export_df = df.drop(columns=["geometry"]) if "geometry" in df.columns else df
        if "village_id" in export_df.columns:
            export_df = export_df.copy()
            dig = export_df["village_id"].astype(str)
            numeric = dig[dig.str.fullmatch(r"\d+")]
            width = int(numeric.str.len().max()) if len(numeric) else 6
            width = max(width, 6)
            export_df["village_id"] = dig.apply(
                lambda x: x.zfill(width) if x.isdigit() else x
            )
            if "village_id" in df.columns and "geometry" in df.columns:
                df["village_id"] = export_df["village_id"].values
        export_df.to_csv(csv_path, index=False)
        print(f"  CSV saved: {csv_path}")
        geojson_path = OUTPUT_DIR / f"village_risk_{output_name}.geojson"
        df.to_file(geojson_path, driver="GeoJSON")
        print(f"  GeoJSON saved: {geojson_path}")
        for col in ["flood_score", "landslide_score", "cloudburst_score",
                     "coastal_erosion_score", "multi_hazard",
                     "risk_category", "red_zone_status", "risk_confidence"]:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                raster_path = OUTPUT_DIR / f"{col}_{output_name}.tif"
                self._vector_to_raster(df, col, raster_path)
                print(f"  Raster saved: {raster_path}")
        return {
            "csv": str(csv_path),
            "geojson": str(geojson_path),
            "records": len(df),
            "red_zone_counts": df["red_zone_status"].value_counts().to_dict(),
            "mean_multi_hazard": float(df["multi_hazard"].mean()),
        }

    def _vector_to_raster(self, gdf, column, output_path, resolution=0.003):
        bounds = gdf.total_bounds
        width = max(1, int((bounds[2] - bounds[0]) / resolution))
        height = max(1, int((bounds[3] - bounds[1]) / resolution))
        transform = from_origin(bounds[0], bounds[3], resolution, resolution)
        arr = np.zeros((height, width), dtype="float32")
        for idx, row in gdf.iterrows():
            geom = row["geometry"]
            env = geom.envelope
            j0 = int((env.bounds[0] - bounds[0]) / resolution)
            j1 = int((env.bounds[2] - bounds[0]) / resolution)
            i0 = int((bounds[3] - env.bounds[3]) / resolution)
            i1 = int((bounds[3] - env.bounds[1]) / resolution)
            j0, j1 = max(0, j0), min(width - 1, j1)
            i0, i1 = max(0, i0), min(height - 1, i1)
            if i0 <= i1 and j0 <= j1:
                val = row[column]
                if pd.notna(val):
                    arr[i0:i1+1, j0:j1+1] = float(val)
        with rasterio.open(str(output_path), "w", driver="GTiff",
                           height=height, width=width, count=1,
                           dtype="float32", crs="EPSG:4326", transform=transform) as out:
            out.write(arr, 1)

    def run_all(self):
        print(f"\n{'#'*60}")
        print(f"# MODULE 1: HAZARD INTELLIGENCE PIPELINE")
        print(f"# State: {self.state} | District: {self.district}")
        print(f"# GEE Project: {GEE_PROJECT}")
        print(f"{'#'*60}")
        self.step1_village_layer()
        self.step2_dem_layer()
        self.step3_rainfall_layer()
        self.step4_flood_risk()
        self.step5_landslide_risk()
        self.step6_cloudburst_risk()
        self.step7_coastal_risk()
        self.step8_village_aggregation()
        self.step9_red_zone_generation()
        return self.step10_export()

    @staticmethod
    def _raster_to_array(path):
        with rasterio.open(path) as src:
            return src.read(1).astype(float)
