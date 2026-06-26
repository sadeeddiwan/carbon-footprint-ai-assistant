"""
Aggregation & Trend Analysis — Carbon Footprint AI Assistant
Groups enriched trip records by ISO week and computes weekly summaries.
"""

from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emissions_calculator import process_csv


def get_week(date_str: str) -> int:
    """Convert YYYY-MM-DD to ISO week number."""
    return datetime.strptime(date_str, "%Y-%m-%d").isocalendar()[1]


def aggregate(records: list) -> list:
    """
    Group records by week, compute totals and trend.

    Returns list of weekly summary dicts ordered by week number.
    Each dict contains:
        week, total_co2e, by_mode, dominant_mode, dominant_pct,
        prev_total, change_pct, trend
    """
    # Group by week
    weeks: dict = {}
    for r in records:
        w = get_week(r["date"])
        if w not in weeks:
            weeks[w] = {"total": 0.0, "by_mode": {}}
        weeks[w]["total"] += r["co2e_grams"]
        mode = r["transport_mode"]
        weeks[w]["by_mode"][mode] = weeks[w]["by_mode"].get(mode, 0.0) + r["co2e_grams"]

    summaries = []
    prev_total = None

    for week_num in sorted(weeks):
        total   = round(weeks[week_num]["total"], 1)
        by_mode = {m: round(v, 1)
                   for m, v in sorted(weeks[week_num]["by_mode"].items(),
                                      key=lambda x: x[1], reverse=True)}

        dominant     = max(by_mode, key=by_mode.get)
        dominant_pct = round(by_mode[dominant] / total * 100) if total > 0 else 0

        if prev_total is None:
            change, trend = 0.0, "first week"
        else:
            change = round((total - prev_total) / prev_total * 100, 1)
            if change > 5:
                trend = "increasing"
            elif change < -5:
                trend = "decreasing"
            else:
                trend = "stable"

        summaries.append({
            "week":          week_num,
            "total_co2e":    total,
            "by_mode":       by_mode,
            "dominant_mode": dominant,
            "dominant_pct":  dominant_pct,
            "prev_total":    prev_total,
            "change_pct":    change,
            "trend":         trend,
        })
        prev_total = total

    return summaries


def determine_branch(summary: dict) -> str:
    """
    Returns which n8n branch this week would take.
    'critical' → Switch Output 1 → alert message
    'standard' → Switch fallback → normal briefing
    """
    if summary["trend"] == "increasing" and summary["change_pct"] > 10:
        return "critical"
    return "standard"


if __name__ == "__main__":
    import json

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "data", "synthetic_data.csv")

    print("=" * 65)
    print("CARBON FOOTPRINT — WEEKLY AGGREGATION & BRANCH DECISIONS")
    print("=" * 65)

    records   = process_csv(path)
    summaries = aggregate(records)

    for s in summaries:
        branch = determine_branch(s)
        icon   = "⚠️  CRITICAL" if branch == "critical" else "🌍 STANDARD"

        print(f"\nWeek {s['week']}")
        print(f"  Total CO2e:    {s['total_co2e']:>10,.1f} gCO2e")
        if s["prev_total"]:
            print(f"  Previous week: {s['prev_total']:>10,.1f} gCO2e")
            print(f"  Change:        {s['change_pct']:>+10.1f}%")
        print(f"  Trend:         {s['trend']}")
        print(f"  Dominant mode: {s['dominant_mode']} ({s['dominant_pct']}%)")
        print(f"  By mode:       {json.dumps(s['by_mode'])}")
        print(f"  ─── Branch → {icon}")

    print()
    print("=" * 65)
    print("BRANCH SUMMARY")
    print("=" * 65)
    for s in summaries:
        branch = determine_branch(s)
        label  = "⚠️  ALERT (Critical)" if branch == "critical" else "🌍 Normal (Standard)"
        print(f"  Week {s['week']}: {s['change_pct']:>+6.1f}% | {s['trend']:<12} → {label}")
