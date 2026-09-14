import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

import geopandas as gpd

from backend.config.settings import PROCESSED_DIR, GEE_OUTPUT_DIR

app = FastAPI(title="SIH 2026 - Multi-Hazard Red Zone API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Simple demo auth (for the SIH demo portal). Replace with real JWT later.
# ---------------------------------------------------------------------------
DEMO_USER = "sih"
DEMO_PASS = "sih2026"


class LoginBody(BaseModel):
    username: str
    password: str


def _json_safe(value):
    """Recursively convert NaN/Inf floats so responses pass json.dumps."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


@app.post("/api/login")
def login(body: LoginBody):
    if body.username == DEMO_USER and body.password == DEMO_PASS:
        return {"token": "demo-token-sih", "username": body.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")


def require_auth(authorization: Optional[str] = Header(default=None)):
    if not authorization or authorization != "Bearer demo-token-sih":
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# District discovery - scans the processed folders, so any new district the
# user adds appears automatically.
# ---------------------------------------------------------------------------

def _discover_districts():
    districts = []
    for csv_path in sorted(PROCESSED_DIR.glob("village_risk_*.csv")):
        key = csv_path.stem.replace("village_risk_", "")
        geojson = GEE_OUTPUT_DIR / f"village_risk_{key}.geojson"
        districts.append({
            "key": key,
            "csv": str(csv_path),
            "geojson": str(geojson) if geojson.exists() else None,
        })
    return districts


@app.get("/api/districts")
def list_districts(authorization: Optional[str] = Header(default=None)):
    require_auth(authorization)
    dists = _discover_districts()
    for d in dists:
        gdf = gpd.read_file(d["geojson"]) if d["geojson"] else gpd.GeoDataFrame()
        d["state"] = str(gdf["state"].iloc[0]) if len(gdf) and "state" in gdf.columns else d["key"]
        d["village_count"] = len(gdf)
        if len(gdf) and "red_zone_status" in gdf.columns:
            d["red_zone_counts"] = gdf["red_zone_status"].value_counts().to_dict()
        else:
            d["red_zone_counts"] = {}
    return {"districts": dists}


# ---------------------------------------------------------------------------
# Village-level data for a district (Module 1 output)
# ---------------------------------------------------------------------------

@app.get("/api/districts/{key}/villages")
def village_geojson(key: str, authorization: Optional[str] = Header(default=None)):
    require_auth(authorization)
    geojson = GEE_OUTPUT_DIR / f"village_risk_{key}.geojson"
    if not geojson.exists():
        raise HTTPException(status_code=404, detail=f"No data for district '{key}'")
    import json as _json
    return _json.loads(gpd.read_file(geojson).to_json())


@app.get("/api/districts/{key}/table")
def village_table(key: str, limit: int = 1000, authorization: Optional[str] = Header(default=None)):
    require_auth(authorization)
    csv_file = PROCESSED_DIR / f"village_risk_{key}.csv"
    if not csv_file.exists():
        raise HTTPException(status_code=404, detail=f"No data for district '{key}'")
    import pandas as pd
    df = pd.read_csv(csv_file, dtype={"village_id": str})
    df = df.sort_values("multi_hazard", ascending=False).head(limit)
    rows = [_json_safe(r) for r in df.to_dict(orient="records")]
    return {"district": key, "rows": rows}


@app.get("/api/districts/{key}/villages/{village_id}")
def village_detail(key: str, village_id: str, authorization: Optional[str] = Header(default=None)):
    require_auth(authorization)
    geojson = GEE_OUTPUT_DIR / f"village_risk_{key}.geojson"
    if not geojson.exists():
        raise HTTPException(status_code=404, detail=f"No data for district '{key}'")
    gdf = gpd.read_file(geojson)
    if "village_id" not in gdf.columns:
        gdf["village_id"] = gdf["name"].astype(str)
    match = gdf[gdf["village_id"].astype(str) == str(village_id)]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Village '{village_id}' not found")
    row = match.iloc[0]
    props = {k: (None if str(v) in ("nan", "None") else v) for k, v in row.drop("geometry").to_dict().items()}
    return {"village": props, "geometry": row["geometry"].__geo_interface__}


@app.get("/api/search")
def search_villages(q: str = "", limit: int = 50, authorization: Optional[str] = Header(default=None)):
    require_auth(authorization)
    q = q.strip().lower()
    if not q:
        return {"results": []}
    results = []
    for d in _discover_districts():
        if not d["geojson"]:
            continue
        gdf = gpd.read_file(d["geojson"])
        name_col = "name" if "name" in gdf.columns else None
        if name_col:
            name_series = gdf[name_col].astype(str)
            mask = name_series.str.lower().str.contains(q)
            hits = gdf[mask].head(limit)
            for _, r in hits.iterrows():
                results.append({
                    "village_id": str(r.get("village_id", "")),
                    "name": str(r.get(name_col, "")),
                    "district": d["key"],
                    "state": str(r.get("state", "")),
                    "red_zone_status": str(r.get("red_zone_status", "")),
                    "multi_hazard": round(float(r.get("multi_hazard", 0)) or 0, 3),
                })
    return {"results": results}


@app.get("/api/health")
def health():
    return {"status": "ok", "districts": [d["key"] for d in _discover_districts()]}