import unittest
from unittest.mock import patch

import sizing

# Any of these in a response would put a machine-chosen position size in
# front of the owner, which is the owner's decision to make, not the
# machine's. sizing.suggest() must never emit one.
MACHINE_SIZED_FIELDS = (
    "shares",
    "suggested_value",
    "risk_amount",
    "actual_alloc_pct",
    "actual_planned_risk_pct",
    "value_by_risk_cap",
    "binding_cap",
    "actionable",
    "kelly_pct",
    "half_kelly_pct",
    "p_win",
    "payoff_b",
)


class SizingSafetyTests(unittest.TestCase):
    def assert_no_machine_size(self, out):
        leaked = [k for k in MACHINE_SIZED_FIELDS if k in out]
        self.assertEqual(leaked, [], f"machine-chosen size leaked: {leaked}")

    def test_unknown_regime_fails_closed_and_emits_no_quantity(self):
        with patch.object(sizing, "_regime_scale",
                          return_value=(0.0, "UNKNOWN", "regime unavailable")):
            out = sizing.suggest("ABC", trigger=100, stop=95, capital=100000)
        self.assertEqual(out["planned_risk_budget_pct"], 0.0)
        self.assertEqual(out["alloc_pct"], 0.0)
        self.assertEqual(out["max_position_value"], 0.0)
        self.assertEqual(out["reason"], "regime unavailable")
        self.assert_no_machine_size(out)

    def test_caps_apply_after_quality_and_regime_multipliers(self):
        with patch.object(sizing, "_regime_scale",
                          return_value=(0.5, "WEAK", None)):
            out = sizing.suggest("ABC", trigger=100, stop=95,
                                 capital=100000, shape_score=80)
        self.assertLessEqual(out["alloc_pct"], 25.0)
        self.assertLessEqual(out["planned_risk_budget_pct"], 1.0)
        self.assertGreater(out["planned_risk_budget_pct"], 0.0)
        self.assert_no_machine_size(out)

    def test_invalid_prices_report_a_reason_and_no_quantity(self):
        with patch.object(sizing, "_regime_scale",
                          return_value=(1.0, "BULL", None)):
            out = sizing.suggest("ABC", trigger=100, stop=100, capital=100000)
        self.assertIn("above stop", out["reason"])
        self.assertNotIn("risk_pct", out)
        self.assert_no_machine_size(out)

    def test_stop_distance_is_reported_but_never_a_size(self):
        with patch.object(sizing, "_regime_scale",
                          return_value=(1.0, "BULL", None)):
            out = sizing.suggest("ABC", trigger=100, stop=95, capital=100000)
        self.assertEqual(out["risk_pct"], 5.0)
        self.assert_no_machine_size(out)

    def test_position_ceiling_stays_inside_the_config_cap(self):
        with patch.object(sizing, "_regime_scale",
                          return_value=(1.0, "BULL", None)):
            out = sizing.suggest("ABC", capital=100000, shape_score=100)
        self.assertLessEqual(out["max_position_value"], 100000 * 0.25)
        self.assert_no_machine_size(out)


if __name__ == "__main__":
    unittest.main()
