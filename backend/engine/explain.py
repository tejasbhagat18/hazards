"""Translate stored village scores into the public risk-explanation contract."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from backend.engine.contracts import confidence_level, make_hazard_assessment, score_level
from backend.fusion.red_zone import METHODOLOGY, MODEL_VERSION, assessment_confidence


HAZARDS = (
    ("flood", "flood_score", "Flood susceptibility", ["GFSM flood susceptibility layer"]),
    ("landslide", "landslide_score", "Landslide susceptibility", ["ILSM landslide susceptibility layer", "SRTM terrain"]),
    ("extreme_rainfall", "cloudburst_score", "Extreme Rainfall / Cloudburst Risk Indicator", ["CHIRPS historical rainfall", "GPM IMERG monthly rainfall", "SRTM terrain", "HydroSHEDS drainage"]),
    ("coastal_erosion_exposure", "coastal_erosion_score", "Coastal Erosion Exposure Indicator", ["Coastline proximity (screening indicator)"]),
)


def _number(value: Any) -> float | None:
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _factor_label(score: float | None) -> str:
    return score_level(score)


def village_risk_profile(row: dict[str, Any], district: str) -> dict[str, Any]:
    location_id = str(row.get("village_id", ""))
    hazards = []
    missing_all: list[str] = []
    for hazard_type, column, label, sources in HAZARDS:
        score = _number(row.get(column))
        missing = [] if score is not None else [label]
        factors = {} if score is None else {label: _factor_label(score)}
        assessment = make_hazard_assessment(
            location_id=location_id,
            hazard_type=hazard_type,
            score=score,
            factors=factors,
            data_sources=sources if score is not None else [],
            missing_data=missing,
        ).to_dict()
        assessment["display_name"] = label
        hazards.append(assessment)
        missing_all.extend(missing)

    overall = _number(row.get("multi_hazard"))
    available = [h["hazard_score"] for h in hazards if h["hazard_score"] is not None]
    confidence = assessment_confidence(row)
    contributors = sorted(
        (
            {"hazard_type": h["hazard_type"], "label": h["display_name"], "score": h["hazard_score"], "level": h["risk_level"]}
            for h in hazards if h["hazard_score"] is not None
        ), key=lambda item: item["score"], reverse=True,
    )[:3]
    return {
        "location_id": location_id,
        "location": {"name": row.get("name"), "district": district, "state": row.get("state")},
        "overall_risk_score": overall,
        "overall_risk_level": row.get("risk_category") or score_level(overall),
        "red_zone_status": row.get("red_zone_status"),
        "risk_confidence": confidence,
        "risk_confidence_level": confidence_level(confidence),
        "hazards": hazards,
        "top_contributors": contributors,
        "missing_data": missing_all,
        "assessment_mode": "demo_static",
        "data_timestamp": row.get("assessment_generated_at") or datetime.now(timezone.utc).isoformat(),
        "data_sources": sorted({source for h in hazards for source in h["data_sources"]}),
        "method": METHODOLOGY,
        "model_version": MODEL_VERSION,
        "data_version": row.get("data_version", "static-demo-2026"),
        "available_hazard_count": len(available),
    }
