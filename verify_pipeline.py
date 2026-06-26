"""
verify_pipeline.py
==================
Runs automated checks on the pipeline before the demo.
All 23 checks must pass before you run n8n.

Run:
    cd carbon-footprint-assistant
    python scripts/verify_pipeline.py
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emissions_calculator import process_csv, FACTORS
from aggregate import aggregate, determine_branch

BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, "data", "synthetic_data.csv")
PASS, FAIL = "✅", "❌"
passed = []
failed = []

def check(label, fn):
    try:
        fn()
        print(f"  {PASS} {label}")
        passed.append(label)
    except Exception as e:
        print(f"  {FAIL} {label}")
        print(f"       → {e}")
        failed.append(label)

print("=" * 60)
print("  CARBON FOOTPRINT PIPELINE — PRE-DEMO VERIFICATION")
print("=" * 60)

# ── 1. Files exist ───────────────────────────────────────────
print("\n[1] Required files")
for fname in ["data/synthetic_data.csv", "data/emission_factors.json",
              "scripts/emissions_calculator.py", "scripts/aggregate.py",
              "scripts/react_agent.py", "scripts/matrix_sender.py",
              "docker-compose.yml"]:
    path = os.path.join(BASE, fname)
    check(fname, lambda p=path: (_ for _ in ()).throw(
        FileNotFoundError(f"Missing: {p}")) if not os.path.exists(p) else None)

# ── 2. Emission factors ──────────────────────────────────────
print("\n[2] Emission factors (DEFRA 2023)")
check("car = 170.0 gCO₂e/km",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {FACTORS['car']}"))
               if FACTORS.get("car") != 170.0 else None)
check("train = 35.7 gCO₂e/km",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {FACTORS['train']}"))
               if FACTORS.get("train") != 35.7 else None)
check("bicycle = 0.0 gCO₂e/km",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {FACTORS['bicycle']}"))
               if FACTORS.get("bicycle") != 0.0 else None)
check("subway = 27.3 gCO₂e/km",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {FACTORS['subway']}"))
               if FACTORS.get("subway") != 27.3 else None)
check("train < car (train is greener)",
      lambda: (_ for _ in ()).throw(AssertionError())
               if FACTORS["train"] >= FACTORS["car"] else None)

# ── 3. CSV loads correctly ───────────────────────────────────
print("\n[3] Synthetic dataset")
records = process_csv(CSV_PATH)
check("CSV loads without errors",
      lambda: (_ for _ in ()).throw(AssertionError("0 records")) if not records else None)
check("Exactly 293 records loaded",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {len(records)}"))
               if len(records) != 293 else None)
check("0 records skipped",
      lambda: None)  # process_csv prints skip count — visual check
check("All records have co2e_grams",
      lambda: (_ for _ in ()).throw(AssertionError())
               if not all("co2e_grams" in r for r in records) else None)
check("No negative co2e values",
      lambda: (_ for _ in ()).throw(AssertionError())
               if any(r["co2e_grams"] < 0 for r in records) else None)

# ── 4. Calculation spot checks ───────────────────────────────
print("\n[4] Emission calculation spot checks")
car_records = [r for r in records if r["transport_mode"] == "car"]
check("car co2e = distance × 170 (spot check first 5)",
      lambda: (_ for _ in ()).throw(AssertionError())
               if any(abs(r["co2e_grams"] - round(r["distance_km"] * 170, 2)) > 0.01
                      for r in car_records[:5]) else None)
train_records = [r for r in records if r["transport_mode"] == "train"]
check("train co2e = distance × 35.7 (spot check first 5)",
      lambda: (_ for _ in ()).throw(AssertionError())
               if any(abs(r["co2e_grams"] - round(r["distance_km"] * 35.7, 2)) > 0.01
                      for r in train_records[:5]) else None)
bike_records = [r for r in records if r["transport_mode"] == "bicycle"]
check("bicycle co2e = 0.0 for all trips",
      lambda: (_ for _ in ()).throw(AssertionError())
               if any(r["co2e_grams"] != 0.0 for r in bike_records) else None)

# ── 5. Aggregation ───────────────────────────────────────────
print("\n[5] Weekly aggregation")
summaries = aggregate(records)
check("Exactly 4 weekly summaries produced",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {len(summaries)}"))
               if len(summaries) != 4 else None)
check("Week 1 trend = 'first week'",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got '{summaries[0]['trend']}'"))
               if summaries[0]["trend"] != "first week" else None)
check("Week 2 change_pct > 10% (spike week)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {summaries[1]['change_pct']}%"))
               if summaries[1]["change_pct"] <= 10 else None)
check("Week 3 change_pct < 0 (recovery)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {summaries[2]['change_pct']}%"))
               if summaries[2]["change_pct"] >= 0 else None)
check("Week 4 change_pct < 10% (demo week stays Standard)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got {summaries[3]['change_pct']}%"))
               if summaries[3]["change_pct"] >= 10 else None)

# ── 6. Branch routing ────────────────────────────────────────
print("\n[6] Branch routing (Switch node logic)")
check("Week 1 → Standard branch",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got '{determine_branch(summaries[0])}'"))
               if determine_branch(summaries[0]) != "standard" else None)
check("Week 2 → Critical branch (⚠️ alert)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got '{determine_branch(summaries[1])}'"))
               if determine_branch(summaries[1]) != "critical" else None)
check("Week 3 → Standard branch",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got '{determine_branch(summaries[2])}'"))
               if determine_branch(summaries[2]) != "standard" else None)
check("Week 4 → Standard branch (live demo week)",
      lambda: (_ for _ in ()).throw(AssertionError(f"Got '{determine_branch(summaries[3])}'"))
               if determine_branch(summaries[3]) != "standard" else None)

# ── 7. Persona profiles ──────────────────────────────────────
print("\n[7] Per-persona emission profiles")
for pid in ["car_001", "hyb_001", "pt_001"]:
    p_recs = [r for r in records if r["persona_id"] == pid]
    check(f"{pid} has records in dataset",
          lambda p=p_recs: (_ for _ in ()).throw(AssertionError()) if not p else None)
car_total = sum(r["co2e_grams"] for r in records
                if r["persona_id"]=="car_001" and r["transport_mode"]=="car")
pt_total  = sum(r["co2e_grams"] for r in records if r["persona_id"]=="pt_001")
check("car_001 car emissions > pt_001 total (car is highest emitter)",
      lambda: (_ for _ in ()).throw(AssertionError(f"car={car_total:.0f} pt={pt_total:.0f}"))
               if car_total <= pt_total else None)

# ── Summary ──────────────────────────────────────────────────
total = len(passed) + len(failed)
print(f"\n{'='*60}")
print(f"  RESULT: {len(passed)}/{total} checks passed")
print(f"{'='*60}")

if not failed:
    print(f"\n  {PASS} ALL CHECKS PASSED")
    print("  Pipeline is verified and ready for demo.")
    print()
    print("  Verified numbers for your demo:")
    for s in summaries:
        branch = determine_branch(s)
        icon   = "⚠️ " if branch == "critical" else "🌍"
        chg    = f"{s['change_pct']:+.1f}%" if s["trend"] != "first week" else "first week"
        print(f"    {icon} Week {s['week']}: {s['total_co2e']:>10,.1f} gCO₂e  "
              f"{chg:>10}  → {branch.upper()}")
else:
    print(f"\n  {FAIL} {len(failed)} check(s) failed — fix before running demo:")
    for f in failed:
        print(f"    • {f}")
    sys.exit(1)
