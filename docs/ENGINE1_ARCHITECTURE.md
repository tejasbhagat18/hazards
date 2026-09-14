# Hazard Intelligence Engine (Engine 1)

Engine 1 is an offline/static, reproducible assessment engine. It does not claim live sensing, real-time forecasting, disaster prediction, or relocation decisions.

## Outputs

For each village it emits normalized hazard indicators, a weighted multi-hazard risk score, risk category, confidence, contributing factors, source provenance, timestamp, method and model version. `GET /api/districts/{district}/villages/{village_id}/risk` returns the integration-ready profile; `GET /api/risk/{location_id}?district={district}` is its location-oriented alias.

`flood_score` is flood susceptibility, with GFSM as its primary evidence. `landslide_score` is a landslide susceptibility indicator. `cloudburst_score` is labelled **Extreme Rainfall / Cloudburst Risk Indicator**, not a forecast. `coastal_erosion_score` is labelled **Coastal Erosion Exposure**; proximity alone is not an erosion prediction.

## Missing data and confidence

Missing source data remains missing. Fusion re-normalizes only across available indicators and reduces `risk_confidence` by the unavailable hazard weight. It never treats unavailable data as a zero-risk value.

## Configuration and reproducibility

The operational method is `Multi-Hazard Weighted Index (authority-configurable scenario weights)`, version `hie-v1.0`. Override scenario weights without code edits using `HIE_WEIGHT_FLOOD`, `HIE_WEIGHT_LANDSLIDE`, `HIE_WEIGHT_CLOUDBURST`, and `HIE_WEIGHT_COASTAL`; `HIE_MODEL_VERSION` sets the recorded version. Values should be agreed by the responsible authority.

The existing ML notebooks remain experimental comparison work only. They are not imported by, or required for, the operational application. Exposure/vulnerability belongs to Engine 2 and relocation decisions belong to Engines 3--4.
