"""Stable, machine-readable outputs shared by all Hazard Intelligence modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


RISK_LEVELS = ("Low", "Moderate", "High", "Very High")


def score_level(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    if value < 0.25:
        return "Low"
    if value < 0.50:
        return "Moderate"
    if value < 0.75:
        return "High"
    return "Very High"


def confidence_level(value: float) -> str:
    if value >= 0.80:
        return "High"
    if value >= 0.50:
        return "Medium"
    return "Low"


@dataclass(frozen=True)
class HazardAssessment:
    """One hazard's normalized assessment for one location.

    Scores are always 0--1 internally.  Missing evidence is represented by
    ``None`` and listed in ``missing_data``; it is never silently converted to
    a low-risk score.
    """

    location_id: str
    hazard_type: str
    hazard_score: float | None
    risk_level: str
    confidence: float
    confidence_level: str
    factors: dict[str, str]
    data_sources: list[str]
    missing_data: list[str]
    data_timestamp: str
    assessment_mode: str = "demo_static"
    method: str = "Hazard Intelligence Engine"
    model_version: str = "hie-v1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_hazard_assessment(
    *,
    location_id: str,
    hazard_type: str,
    score: float | None,
    factors: dict[str, str],
    data_sources: list[str],
    missing_data: list[str] | None = None,
    assessment_mode: str = "demo_static",
) -> HazardAssessment:
    missing = missing_data or []
    bounded = None if score is None else max(0.0, min(1.0, float(score)))
    # Evidence completeness is intentionally simple and auditable.  It can be
    # replaced later by authority-calibrated, source-specific quality weights.
    evidence_count = len(factors) + len(missing)
    confidence = (len(factors) / evidence_count) if evidence_count else 0.0
    return HazardAssessment(
        location_id=str(location_id),
        hazard_type=hazard_type,
        hazard_score=bounded,
        risk_level=score_level(bounded),
        confidence=round(confidence, 3),
        confidence_level=confidence_level(confidence),
        factors=factors,
        data_sources=data_sources,
        missing_data=missing,
        data_timestamp=datetime.now(timezone.utc).isoformat(),
        assessment_mode=assessment_mode,
    )
