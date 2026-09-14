import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata.kernelspec = {"name": "python3", "display_name": "Python 3", "language": "python"}
nb.metadata.language_info = {"name": "python", "version": "3"}

cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# Fusion Engine + Red Zone Generator (Module 1, Part B)

This is **the integrated model**. Layer 1 gave every village 4 features:

- `flood_score` (from the GFSM flood map)
- `landslide_score` (from the ILSM landslide map)
- `coastal_erosion_score` (distance to coast + erosion band)
- `cloudburst_score` (terrain + extreme rainfall)

This notebook trains the model that turns those 4 numbers into:

- **Multi-Hazard Score**
- **Risk Category** (Low / Moderate / High / Very High)
- **Red Zone Status** (GREEN / ORANGE / RED)

Two methods are built side by side:

1. **AHP expert weights** — transparent rule-based fusion (used as the baseline)
2. **Learned model** — Random Forest / Logistic Regression trained on historical
   disaster labels (used once real NDRF records are available)
"""
))

cells.append(nbf.v4.new_code_cell(
"""import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, classification_report

from backend.config.settings import OUTPUT_DIR

FEATURES = ["flood_score", "landslide_score", "coastal_erosion_score", "cloudburst_score"]
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## 1. Load the village scores

`village_risk.csv` is produced by `python backend/run_pipeline.py`.
Rows where a raster did not cover the village got `NaN` - we drop them
(few in practice)."""
))

cells.append(nbf.v4.new_code_cell(
"""from backend.config import settings

df = pd.read_csv(settings.OUTPUT_FILE)
df = df.dropna(subset=FEATURES).reset_index(drop=True)
df[["village_id", *FEATURES]].head()
"""
))

cells.append(nbf.v4.new_code_cell(
"""df[FEATURES].describe().round(3)
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## 2. Method A - AHP expert weights (baseline)

Weights come from an expert pairwise-comparison matrix (AHP). For now we use the
defaults that sum to 1. You can edit them and re-run."""
))

cells.append(nbf.v4.new_code_cell(
"""WEIGHTS = {"flood": 0.35, "landslide": 0.30, "cloudburst": 0.15, "coastal": 0.20}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

def multihazard(row, w=WEIGHTS):
    return (w["flood"] * row["flood_score"]
            + w["landslide"] * row["landslide_score"]
            + w["cloudburst"] * row["cloudburst_score"]
            + w["coastal"] * row["coastal_erosion_score"])

df["mh_ahp"] = df.apply(multihazard, axis=1).clip(0, 1)

def category(score):
    return ["Low", "Moderate", "High", "Very High"][
        int(score >= 0.75) + int(score >= 0.50) + int(score >= 0.25)]

def redzone(cat):
    return {"Very High": "RED", "High": "ORANGE",
            "Moderate": "YELLOW", "Low": "GREEN"}[cat]

df["risk_category"] = df["mh_ahp"].apply(category)
df["red_zone_status"] = df["risk_category"].apply(redzone)
df[["village_id", *FEATURES, "mh_ahp", "risk_category", "red_zone_status"]]
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## 3. Method B - Learned model

We need a **supervised label**: did this village actually get hit by a disaster?

- When NDRF / state disaster records are available, load them and join on
  `village_id`. A village in the records gets `label = 1`.
- Until then, we create a **placeholder label** from the baseline scores with a
  clear rule, so the training pipeline is fully demonstrated. Replace the
  `build_labels()` block with your real records file later.

The label below says: a village is `1` if it is Very High by the AHP score OR
high on both flood and landslide - a reasonable default."""
))

cells.append(nbf.v4.new_code_cell(
"""LABELS_CSV = None  # set to a real records CSV path when available
REAL_LABEL_COL = "disaster_flag"

def build_labels(d):
    if LABELS_CSV is not None:
        rec = pd.read_csv(LABELS_CSV)
        m = d.merge(rec[["village_id", REAL_LABEL_COL]], on="village_id", how="left")
        m[REAL_LABEL_COL] = m[REAL_LABEL_COL].fillna(0).astype(int)
        return m[REAL_LABEL_COL].values
    return ((
        (d["mh_ahp"] >= 0.55)
        | ((d["flood_score"] >= 0.55) & (d["landslide_score"] >= 0.55))
    ).astype(int)).values

df["label"] = build_labels(df)
print("positive labels:", int(df["label"].sum()), "of", len(df))
df[["village_id", "mh_ahp", "label"]]
"""
))

cells.append(nbf.v4.new_code_cell(
"""X = df[FEATURES].values
y = df["label"].values
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, stratify=y, random_state=42)
print("train positive:", y_train.mean().round(3), "| test positive:", y_test.mean().round(3))
"""
))

cells.append(nbf.v4.new_code_cell(
"""models = {
    "RandomForest": RandomForestClassifier(n_estimators=300, max_depth=6, random_state=42),
    "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
}

def cv_auc(est, Xs, ys, cv=5):
    return cross_val_score(est, Xs, ys, cv=cv, scoring="roc_auc")

scores = {}
for name, est in models.items():
    a = cv_auc(est, X_train, y_train)
    scores[name] = a.mean()
    print(f"{name}: CV ROC-AUC = {a.mean():.3f}  (+/- {a.std():.3f})")

best_name = max(scores, key=scores.get)
print("best model:", best_name, scores[best_name])
"""
))

cells.append(nbf.v4.new_code_cell(
"""best = models[best_name]
best.fit(X_train, y_train)
pred = best.predict_proba(X_test)[:, 1]
print("Test ROC-AUC:", round(roc_auc_score(y_test, pred), 3))
print(classification_report(y_test, best.predict(X_test), target_names=["safe", "hit"]))
print("feature importances (RF only):")
if hasattr(best, "feature_importances_"):
    for f, i in zip(FEATURES, best.feature_importances_):
        print(f"  {f:28s} {i:.3f}")
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## 4. Compare and decide

The learned model and the AHP baseline agree on most villages. We keep the AHP
labels for **explainability** but record the learned model risk too, so judges
see both - and the model becomes the active scorer once real labels arrive."""
))

cells.append(nbf.v4.new_code_cell(
"""df["model_risk"] = best.predict_proba(df[FEATURES].values)[:, 1]
agreement = (df["label"] == (df["mh_ahp"] >= 0.5)).mean()
print(f"label agreement with baseline (>=0.5): {agreement:.2%}")
df[["village_id", "mh_ahp", "model_risk", "label"]]
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## 5. Save outputs

- `fusion_model.joblib` - the trained integrated model (Phase 2 ready)
- `village_redzone.csv` - the final Module 1 table the dashboard reads"""
))

cells.append(nbf.v4.new_code_cell(
"""joblib.dump(best, OUTPUT_DIR / "fusion_model.joblib")
cols = ["village_id", "name", "district", *FEATURES, "mh_ahp", "model_risk",
        "risk_category", "red_zone_status", "label"]
df[cols].to_csv(OUTPUT_DIR / "village_redzone.csv", index=False)
print("saved:", OUTPUT_DIR / "village_redzone.csv")
"""
))

cells.append(nbf.v4.new_code_cell(
"""summary = df.groupby("red_zone_status").agg(
    villages=("village_id", "count"), avg_risk=("mh_ahp", "mean")).round(3)
summary
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## What next (Phase 2 / Phase 3)

- Replace `LABELS_CSV = None` with real NDRF/state disaster incident records - the
  model then learns *true* weights for your district.
- Feed `village_redzone.csv` into the dashboard map (RED/ORANGE/GREEN pins).
- Phase 3 relocation uses these Red Zone villages as its priority input.
"""
))

nb["cells"] = cells
nbf.write(nb, "backend/Fusion_and_RedZone.ipynb")
print("notebook written")