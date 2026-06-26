"""
verify_pipeline.py — Tests everything that can be tested without Ollama or Matrix.
Run this first after cloning to confirm the Python pipeline works correctly.

Usage:
    python scripts/verify_pipeline.py

All checks must pass (✅) before touching n8n or Ollama.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "✅"
FAIL = "❌"
results = []


def check(label, fn):
    try:
        fn()
        print(f"  {PASS} {label}")
        results.append(True)
    except Exception as e:
        print(f"  {FAIL} {label}")
        print(f"      Error: {e}")
        results.append(False)


print("=" * 58)
print("  CARBON FOOTPRINT PIPELINE — VERIFICATION")
print("=" * 58)

# ── 1. Files exist ────────────────────────────────────────────
print("\n[1] Required files")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for fname in [
    "data/emission_factors.json",
    "data/synthetic_data.csv",
    "scripts/emissions_calculator.py",
    "scripts/aggregate.py",
    "scripts/react_agent.py",
    "scripts/matrix_sender.py",
    "docker-compose.yml",
]:
    path = os.path.join(BASE, fname)
    check(fname, lambda p=path: (_ for _ in ()).throw(
        FileNotFoundError(f"Missing: {p}")) if not os.path.exists(p) else None)

# ── 2. Emission factors valid ─────────────────────────────────
print("\n[2] Emission factors")

def check_factors():
    with open(os.path.join(BASE, "data", "emission_factors.json")) as f:
        data = json.load(f)
    factors = {k: v for k, v in data.items() if k != "_meta"}
    assert len(factors) >= 10, f"Only {len(factors)} factors — expected at least 10"
    assert factors["car"] == 170.0, f"Car factor wrong: {factors['car']}"
    assert factors["bicycle"] == 0.0, f"Bicycle factor wrong: {factors['bicycle']}"
    assert "train" in factors, "train factor missing"

check("emission_factors.json loads correctly", check_factors)
check("car = 170.0 gCO2e/km",   lambda: (_ for _ in ()).throw(AssertionError()) if json.load(open(os.path.join(BASE,"data","emission_factors.json")))["car"] != 170.0 else None)
check("bicycle = 0.0 gCO2e/km", lambda: (_ for _ in ()).throw(AssertionError()) if json.load(open(os.path.join(BASE,"data","emission_factors.json")))["bicycle"] != 0.0 else None)

# ── 3. Emissions calculator ───────────────────────────────────
print("\n[3] Emissions calculator")
from emissions_calculator import calculate_co2e, process_csv, get_known_modes

check("calculate_co2e('car', 10.0) = 1700.0",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {calculate_co2e('car', 10.0)}"))
               if calculate_co2e('car', 10.0) != 1700.0 else None)
check("calculate_co2e('bicycle', 10.0) = 0.0",
      lambda: (_ for _ in ()).throw(AssertionError())
               if calculate_co2e('bicycle', 10.0) != 0.0 else None)
check("train CO2e < car CO2e for same distance",
      lambda: (_ for _ in ()).throw(AssertionError())
               if calculate_co2e('train', 10.0) >= calculate_co2e('car', 10.0) else None)
check("Unknown mode returns 0.0",
      lambda: (_ for _ in ()).throw(AssertionError())
               if calculate_co2e('hoverboard', 10.0) != 0.0 else None)

csv_path = os.path.join(BASE, "data", "synthetic_data.csv")

def check_csv_load():
    recs = process_csv(csv_path)
    assert len(recs) > 200, f"Expected >200 records, got {len(recs)}"
    assert all("co2e_grams" in r for r in recs), "co2e_grams missing from records"
    assert all(r["co2e_grams"] >= 0 for r in recs), "Negative CO2e found"

check(f"process_csv loads {csv_path.split('/')[-1]}", check_csv_load)

# ── 4. Aggregation & branching ────────────────────────────────
print("\n[4] Aggregation & branch logic")
from aggregate import aggregate, determine_branch

records   = process_csv(csv_path)
summaries = aggregate(records)

check("Produces 4 weekly summaries",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {len(summaries)}"))
               if len(summaries) != 4 else None)

check("Week 1: trend = first week",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {summaries[0]['trend']}"))
               if summaries[0]["trend"] != "first week" else None)

check("Week 2: change_pct > 10% (Critical branch)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {summaries[1]['change_pct']}%"))
               if summaries[1]["change_pct"] <= 10 else None)

check("Week 2 routes to Critical branch",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {determine_branch(summaries[1])}"))
               if determine_branch(summaries[1]) != "critical" else None)

check("Week 3 routes to Standard branch",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {determine_branch(summaries[2])}"))
               if determine_branch(summaries[2]) != "standard" else None)

check("Week 4 routes to Standard branch (live demo week)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {determine_branch(summaries[3])}"))
               if determine_branch(summaries[3]) != "standard" else None)

check("Week 4: change_pct < 10% (does not trigger Critical)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {summaries[3]['change_pct']}%"))
               if summaries[3]["change_pct"] >= 10 else None)

check("All weeks have dominant_mode set",
      lambda: (_ for _ in ()).throw(AssertionError())
               if not all(s["dominant_mode"] for s in summaries) else None)

# ── 5. Summary ────────────────────────────────────────────────
passed = sum(results)
total  = len(results)

print(f"\n{'='*58}")
print(f"  Results: {passed}/{total} checks passed")
print(f"{'='*58}")

if passed == total:
    print(f"\n  {PASS} ALL CHECKS PASSED")
    print("  The Python pipeline is working correctly.")
    print()
    print("  Next steps:")
    print("  1. Install Ollama and pull mistral:")
    print("     ollama pull mistral")
    print("     python scripts/react_agent.py    (test AI recommendations)")
    print()
    print("  2. Set up Matrix (follow Phase 6 in the guide) then:")
    print("     python scripts/matrix_sender.py  (test Matrix delivery)")
    print()
    print("  3. Build the n8n workflow (follow Phase 7 in the guide):")
    print("     docker-compose up -d")
    print("     open http://localhost:5678")
else:
    print(f"\n  {FAIL} {total - passed} check(s) failed — fix before proceeding.")
    sys.exit(1)

# ── Print weekly summary for reference ───────────────────────
print()
print("  Weekly summary for reference:")
print(f"  {'Week':<6} {'Total CO2e':>12}  {'Change':>8}  {'Branch'}")
print(f"  {'-'*50}")
for s in summaries:
    branch = determine_branch(s)
    icon   = "⚠️ CRITICAL" if branch == "critical" else "🌍 standard"
    change = f"{s['change_pct']:+.1f}%" if s["trend"] != "first week" else "  first"
    print(f"  {s['week']:<6} {s['total_co2e']:>12,.1f}  {change:>8}  {icon}")
print()
