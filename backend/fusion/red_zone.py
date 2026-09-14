DEFAULT_WEIGHTS = {"flood": 0.35, "landslide": 0.30, "coastal": 0.20, "cloudburst": 0.15}
CATEGORY_THRESHOLDS = [0.25, 0.50, 0.75]
CATEGORY_NAMES = ["Low", "Moderate", "High", "Very High"]
RED_ZONE_RULE = {"Very High": "RED", "High": "ORANGE", "Moderate": "YELLOW", "Low": "GREEN"}


def compute_multihazard(df, weights=None):
    w = weights or DEFAULT_WEIGHTS
    out = df.copy()
    total = sum(w.values())
    out["multi_hazard"] = (
        w["flood"] * out["flood_score"]
        + w["landslide"] * out["landslide_score"]
        + w["cloudburst"] * out["cloudburst_score"]
        + w["coastal"] * out["coastal_erosion_score"]
    ) / total
    out["multi_hazard"] = out["multi_hazard"].clip(0, 1)
    return out


def risk_category(score):
    level = sum(score >= t for t in CATEGORY_THRESHOLDS)
    return CATEGORY_NAMES[level]


def red_zone_status(category):
    return RED_ZONE_RULE[category]


def apply_fusion(df, weights=None):
    out = compute_multihazard(df, weights)
    out["risk_category"] = out["multi_hazard"].apply(risk_category)
    out["red_zone_status"] = out["risk_category"].apply(red_zone_status)
    return out