"""Throwaway verification for wisdom.py."""
import json
from traders import wisdom as w

c = w.count()
print(json.dumps(c, indent=2))

assert c["total"] == 76, "expected 76, got " + str(c["total"])
assert c["axioms"] == 5, "expected 5, got " + str(c["axioms"])
assert c["themes"] == 10, "expected 10, got " + str(c["themes"])

# Spot-check the Singhal additions
new_ids = [
    "market_sideways_70pct",
    "confluence_2_3_indicators",
    "never_trade_without_plan",
    "structural_stop_pattern_low",
    "high_vix_skip_trades",
    "first_retracement_only",
    "longer_consolidation_stronger",
    "exit_on_opposite_signal",
    "time_based_exit_intraday",
    "sector_rotation",
    "avoid_overtrading",
    "avoid_analysis_paralysis",
    "trading_journal",
    "start_small",
]
found_ids = {x["id"] for x in w.WISDOM}

for pid in new_ids:
    mark = "OK  " if pid in found_ids else "MISS"
    print(f"  {mark} {pid}")

missing = [p for p in new_ids if p not in found_ids]
assert not missing, "missing: " + ", ".join(missing)
print()
print("ALL CHECKS PASSED")