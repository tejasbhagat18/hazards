"""Configurable, availability-aware Multi-Hazard Risk Index.

This module is the operational (rule/weighted) assessment.  Experimental ML
notebooks are deliberately not imported or used by the application.
"""

from __future__ import annotations

import os

import numpy as np

DEFAULT_WEIGHTS = {"flood": 0.35, "landslide": 0.30, "coastal": 0.20, "cloudburst": 0.15}
MODEL_VERSION = os.getenv("HIE_MODEL_VERSION", "hie-v1.0")
METHODOLOGY = "Multi-Hazard Weighted Index (authority-configurable scenario weights)"
CATEGORY_THRESHOLDS = [0.25, 0.50, 0.75]
CATEGORY_NAMES = ["Low", "Moderate", "High", "Very High"]
RED_ZONE_RULE = {"Very High": "RED", "High": "ORANGE", "Moderate": "YELLOW", "Low": "GREEN"}


def configured_weights():
    """Return scenario/authority-configurable weights from environment when set."""
    values = {}
    for name, default in DEFAULT_WEIGHTS.items():
        try:
            values[name] = float(os.getenv(f"HIE_WEIGHT_{name.upper()}", default))
        except ValueError:
            values[name] = default
    return values


def compute_multihazard(df, weights=None):
    w = weights or configured_weights()
    out = df.copy()
    columns = {"flood": "flood_score", "landslide": "landslide_score", "cloudburst": "cloudburst_score", "coastal": "coastal_erosion_score"}
    numerator = sum(w[name] * out[column].where(out[column].notna(), 0) for name, column in columns.items())
    denominator = sum(w[name] * out[column].notna().astype(float) for name, column in columns.items())
    # No available evidence means no assessment, never a fabricated score of 0.
    out["multi_hazard"] = (numerator / denominator.replace(0, np.nan)).clip(0, 1)
    out["risk_confidence"] = (denominator / sum(w.values())).clip(0, 1)
    out["risk_confidence_level"] = out["risk_confidence"].apply(
        lambda value: "High" if value >= 0.80 else "Medium" if value >= 0.50 else "Low"
    )
    out["missing_hazard_data"] = out.apply(
        lambda row: ", ".join(name for name, column in columns.items() if np.isnan(row[column])), axis=1
    )
    out["multi_hazard"] = out["multi_hazard"].clip(0, 1)
    return out


def risk_category(score):
    if score is None or not np.isfinite(score):
        return "Unavailable"
    level = sum(score >= t for t in CATEGORY_THRESHOLDS)
    return CATEGORY_NAMES[level]


def red_zone_status(category):
    return RED_ZONE_RULE.get(category, "UNKNOWN")


def apply_fusion(df, weights=None):
    out = compute_multihazard(df, weights)
    out["risk_category"] = out["multi_hazard"].apply(risk_category)
    out["red_zone_status"] = out["risk_category"].apply(red_zone_status)
    out["assessment_mode"] = "demo_static"
    out["assessment_method"] = METHODOLOGY
    out["model_version"] = MODEL_VERSION
    return out


def assessment_confidence(row):
    """Read a persisted confidence value, with a safe compatibility fallback."""
    value = row.get("risk_confidence")
    try:
        if value is not None and np.isfinite(float(value)):
            return round(float(value), 3)
    except (TypeError, ValueError):
        pass
    return 1.0
