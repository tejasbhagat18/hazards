import math
import unittest

import pandas as pd

from backend.engine.contracts import make_hazard_assessment
from backend.fusion.red_zone import apply_fusion


class HazardIntelligenceTests(unittest.TestCase):
    def test_missing_hazard_is_not_converted_to_low_risk(self):
        result = apply_fusion(pd.DataFrame([{
            "flood_score": 0.8,
            "landslide_score": math.nan,
            "cloudburst_score": 0.4,
            "coastal_erosion_score": math.nan,
        }]))
        row = result.iloc[0]
        # Available scores are re-normalized: (0.35*.8 + .15*.4) / .5 = .68.
        self.assertAlmostEqual(row["multi_hazard"], 0.68)
        self.assertAlmostEqual(row["risk_confidence"], 0.50)
        self.assertIn("landslide", row["missing_hazard_data"])

    def test_standard_hazard_contract_preserves_missing_evidence(self):
        assessment = make_hazard_assessment(
            location_id="V-1", hazard_type="flood", score=None,
            factors={}, data_sources=[], missing_data=["GFSM flood susceptibility layer"],
        )
        self.assertIsNone(assessment.hazard_score)
        self.assertEqual(assessment.risk_level, "Unavailable")
        self.assertEqual(assessment.confidence_level, "Low")


if __name__ == "__main__":
    unittest.main()
