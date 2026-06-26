"""
evaluate_recommendations.py
============================
Validates that every number in the generated recommendations
traces back to a real, verifiable source in the pipeline data.

Sources checked for each number:
  1. Pipeline output   — dominant_pct, co2e totals, train alternatives
  2. Raw trip records  — distance_km, co2e_grams from CSV
  3. Weekly totals     — aggregated sums per week
  4. DEFRA factors     — emission_factors.json values
  5. Mode percentages  — per-mode share of weekly total
  6. Derived values    — train alternative (distance × 35.7)

Excludes from validation:
  - List numbering (1. 2. 3.)
  - Week reference numbers (e.g. Week 4, Week 5)

Run:
    cd carbon-footprint-assistant
    python scripts/evaluate_recommendations.py
"""

import re, json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emissions_calculator import process_csv, FACTORS
from aggregate import aggregate, get_week

BASE         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH     = os.path.join(BASE, "data", "synthetic_data.csv")
OUT_PATH     = os.path.join(BASE, "data", "recommendation_evaluation.json")
TRAIN_FACTOR = FACTORS["train"]
TOLERANCE    = 1.0


def run_pipeline(persona_id, all_records):
    records      = [r for r in all_records if r["persona_id"] == persona_id]
    summaries    = aggregate(records)
    target       = summaries[-1]
    previous     = summaries[-2] if len(summaries) >= 2 else None
    week_num     = target["week"]
    week_records = [r for r in records if get_week(r["date"]) == week_num]
    by_mode, total = {}, 0.0
    for r in week_records:
        total += r["co2e_grams"]
        by_mode[r["transport_mode"]] = by_mode.get(r["transport_mode"], 0.0) + r["co2e_grams"]
    dom      = max(by_mode, key=by_mode.get)
    dom_pct  = round(by_mode[dom] / total * 100) if total > 0 else 0
    top_trip = sorted(week_records, key=lambda r: r["co2e_grams"], reverse=True)[0] if week_records else None
    return {"persona_id": persona_id, "week": week_num, "records": records,
            "week_records": week_records, "summaries": summaries, "target": target,
            "previous": previous, "by_mode": by_mode, "total_co2e": round(total, 1),
            "dominant_mode": dom, "dominant_pct": dom_pct, "top_trip": top_trip}


def generate_recommendations(ctx):
    tw, dom, dom_pct = ctx["week"], ctx["dominant_mode"], ctx["dominant_pct"]
    dom_co2e = round(ctx["by_mode"][dom], 1)
    total, top, prev = ctx["total_co2e"], ctx["top_trip"], ctx["previous"]
    LOW = {"bicycle", "walking", "e_bicycle"}
    MED = {"train", "subway", "tram", "bus"}
    src = {"dominant_pct": dom_pct, "dominant_co2e": dom_co2e, "current_total": total}

    if dom in LOW:
        r1 = (f"1. Your dominant mode ({dom}) is already zero-emission. "
              f"Focus on eliminating any remaining car or taxi trips.")
    elif dom in MED:
        high = [m for m in ctx["by_mode"] if m not in LOW | MED]
        if high:
            hco2e = round(sum(ctx["by_mode"][m] for m in high), 1)
            src["high_emission_co2e"] = hco2e
            r1 = (f"1. Your main mode ({dom}) is low-emission. "
                  f"Target the remaining {', '.join(high)} trips "
                  f"which produced {hco2e:,.1f} gCO₂e this week.")
        else:
            src["defra_factor_used"] = FACTORS.get(dom)
            r1 = (f"1. Your transport mix is already sustainable — "
                  f"{dom} generates only {FACTORS.get(dom, '?')} gCO₂e/km. "
                  f"Consider replacing any short legs with cycling or walking.")
    else:
        r1 = (f"1. {dom.replace('_',' ').title()} journeys produced "
              f"{dom_pct}% of Week {tw} emissions ({dom_co2e:,.1f} gCO₂e). "
              f"Reducing even one car day per week makes a measurable difference.")

    if top:
        td, tco2e, tm = top["distance_km"], top["co2e_grams"], top["transport_mode"]
        ta     = round(td * TRAIN_FACTOR)
        saving = round(tco2e - ta)
        src.update({"top_trip_distance": td, "top_trip_co2e": tco2e, "train_alternative": ta})
        if tm in LOW | MED:
            r2 = (f"2. Your highest-emission trip was {td} km by {tm} ({tco2e} gCO₂e). "
                  f"Replacing the {td} km leg with cycling or walking saves the full "
                  f"{tco2e} gCO₂e at zero emission.")
        else:
            src["co2e_saving"] = saving
            r2 = (f"2. The highest-emission trip was {td} km by {tm}, "
                  f"producing {tco2e} gCO₂e. "
                  f"Switching to train costs only {ta} gCO₂e — "
                  f"a saving of {saving} gCO₂e on a single journey.")
    else:
        r2 = f"2. No trip data available for Week {tw}."

    if prev:
        pt, chg = prev["total_co2e"], ctx["target"]["change_pct"]
        src.update({"prev_total": pt, "change_pct": abs(chg)})
        dir_ = "higher" if chg > 0 else "lower"
        r3 = (f"3. Emissions were {abs(chg)}% {dir_} than Week {prev['week']} "
              f"({pt:,.1f} → {total:,.1f} gCO₂e). "
              f"Identify which journeys changed and target those next week.")
    else:
        r3 = f"3. Week {tw} ({total:,.1f} gCO₂e) is the baseline. Compare future weeks to track progress."

    return "\n".join([r1, r2, r3]), src


def extract_numbers(text, exclude_weeks=None):
    if exclude_weeks is None:
        exclude_weeks = set()
    cleaned = re.sub(r"(?m)^\s*[123]\.\s+", "", text)
    nums = []
    for n in re.findall(r"[\d,]+\.?\d*", cleaned):
        try:
            val = float(n.replace(",", ""))
            if val <= 0: continue
            if val in {1.0, 2.0, 3.0}: continue
            if val in exclude_weeks: continue
            nums.append(val)
        except ValueError:
            pass
    return list(set(nums))


def trace_number(num, ctx, src):
    res = {"number": num, "found": False, "source_type": None, "explanation": None}
    for field, val in src.items():
        if val is not None and abs(float(val) - num) <= TOLERANCE:
            res.update({"found": True, "source_type": "pipeline_output",
                        "explanation": f"'{field}' = {val} (from aggregation/calculation)"})
            return res
    for r in ctx["week_records"]:
        if abs(r["co2e_grams"] - num) <= TOLERANCE:
            res.update({"found": True, "source_type": "raw_trip_co2e",
                        "explanation": (f"{r['distance_km']}km × "
                                        f"{FACTORS.get(r['transport_mode'],'?')} = "
                                        f"{r['co2e_grams']} ({r['transport_mode']}, {r['date']})")})
            return res
        if abs(r["distance_km"] - num) <= 0.2:
            res.update({"found": True, "source_type": "raw_trip_distance",
                        "explanation": f"trip distance {r['distance_km']}km ({r['transport_mode']}, {r['date']})"})
            return res
    for s in ctx["summaries"]:
        if abs(s["total_co2e"] - num) <= TOLERANCE:
            res.update({"found": True, "source_type": "weekly_total",
                        "explanation": f"Week {s['week']} total = {s['total_co2e']} gCO₂e"})
            return res
    for mode, factor in FACTORS.items():
        if abs(factor - num) <= 0.1:
            res.update({"found": True, "source_type": "defra_factor",
                        "explanation": f"DEFRA 2023 factor for {mode} = {factor} gCO₂e/km"})
            return res
    for r in ctx["week_records"]:
        ta = round(r["distance_km"] * TRAIN_FACTOR)
        if abs(ta - num) <= TOLERANCE:
            res.update({"found": True, "source_type": "derived_train_alternative",
                        "explanation": f"{r['distance_km']}km × {TRAIN_FACTOR} = {ta} gCO₂e"})
            return res
    total = ctx["total_co2e"]
    if total > 0 and 1 <= num <= 100:
        for mode, val in ctx["by_mode"].items():
            pct = round(val / total * 100)
            if abs(pct - num) <= 1:
                res.update({"found": True, "source_type": "mode_percentage",
                            "explanation": f"{mode}: {round(val,1)}/{total} × 100 = {pct}%"})
                return res
    res["explanation"] = "Could not trace to a specific source"
    return res


def main():
    print("=" * 68)
    print("  RECOMMENDATION NUMBER VALIDATION")
    print("  Verifies every number in recommendations traces to real data")
    print(f"  Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 68)

    all_records = process_csv(CSV_PATH)
    personas    = ["car_001", "hyb_001", "pt_001"]
    report      = {"run_timestamp": datetime.now().isoformat(), "personas": {}}
    ov_traced = ov_total = 0

    for pid in personas:
        print(f"\n{'─'*68}")
        print(f"  PERSONA: {pid.upper()}")
        print(f"{'─'*68}")
        ctx = run_pipeline(pid, all_records)
        rec_text, src = generate_recommendations(ctx)
        print(f"\nRecommendation text:\n{rec_text}\n")

        tw = ctx["week"]
        prev_week = ctx["previous"]["week"] if ctx["previous"] else None
        exclude = {float(tw)}
        if prev_week:
            exclude.add(float(prev_week))

        numbers = extract_numbers(rec_text, exclude_weeks=exclude)
        trace_results = []
        traced = failed = 0

        print(f"  {'Number':>14}  {'Source Type':<32}  Explanation")
        print(f"  {'─'*14}  {'─'*32}  {'─'*22}")
        for num in sorted(numbers):
            tr = trace_number(num, ctx, src)
            trace_results.append(tr)
            icon  = "✅" if tr["found"] else "❌"
            exp   = tr["explanation"] or ""
            short = (exp[:48] + "...") if len(exp) > 51 else exp
            print(f"  {num:>14,.1f}  {icon} {(tr['source_type'] or 'not_found'):<30}  {short}")
            if tr["found"]: traced += 1
            else:           failed += 1

        total_n = traced + failed
        pct     = round(traced / total_n * 100) if total_n > 0 else 0
        ov_traced += traced
        ov_total  += total_n
        status = "PASS" if pct == 100 else ("WARN" if pct >= 80 else "FAIL")
        print(f"\n  Numbers extracted : {total_n}")
        print(f"  Fully traced      : {traced}  ({pct}%)")
        print(f"  Not traced        : {failed}")
        print(f"  Status            : {'✅ PASS' if status == 'PASS' else '⚠️  ' + status}")
        report["personas"][pid] = {
            "week": tw, "recommendation": rec_text,
            "numbers_extracted": total_n, "numbers_traced": traced,
            "grounding_pct": pct, "status": status, "trace_details": trace_results}

    ov_pct = round(ov_traced / ov_total * 100) if ov_total > 0 else 0
    final  = "PASS" if ov_pct == 100 else ("WARN" if ov_pct >= 80 else "FAIL")

    print(f"\n{'='*68}")
    print(f"  OVERALL RESULT")
    print(f"{'='*68}")
    for pid in personas:
        p    = report["personas"][pid]
        icon = "✅" if p["status"] == "PASS" else "⚠️ "
        print(f"  {icon} {pid:<12}  {p['grounding_pct']:>3}% grounded  "
              f"({p['numbers_traced']}/{p['numbers_extracted']} numbers traced)")
    print(f"\n  Total numbers validated : {ov_total}")
    print(f"  Total numbers traced    : {ov_traced}")
    print(f"  Overall grounding score : {ov_pct}%")
    print(f"\n  {'✅ ALL RECOMMENDATIONS FULLY DATA-GROUNDED' if final == 'PASS' else '⚠️  REVIEW NEEDED'}")
    print(f"{'='*68}")

    report["summary"] = {
        "total_numbers_validated": ov_total, "total_traced": ov_traced,
        "overall_grounding_pct": ov_pct, "status": final,
        "methodology": (
            "Numbers extracted from recommendation text and traced against: "
            "pipeline outputs (dominant_pct, weekly totals, trip co2e), "
            "raw CSV trip records, DEFRA 2023 emission factors, "
            "derived train alternatives (distance × 35.7), "
            "and mode percentage shares. "
            "Structural numbers (list labels 1/2/3 and week references) excluded. "
            "Tolerance: ±1.0 gCO₂e."
        )
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Report saved → {OUT_PATH}")


if __name__ == "__main__":
    main()
