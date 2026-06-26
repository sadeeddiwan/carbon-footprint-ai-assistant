"""
Emissions Calculator — Carbon Footprint AI Assistant
Loads DEFRA 2023 emission factors and calculates gCO2e per trip.
"""

import json
import csv
import os

# Load factors once at import time
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(_BASE, "data", "emission_factors.json")) as f:
    _DATA    = json.load(f)
    FACTORS  = {k: v for k, v in _DATA.items() if k != "_meta"}
    METADATA = _DATA.get("_meta", {})


def calculate_co2e(transport_mode: str, distance_km: float) -> float:
    """Return grams of CO2e for a single trip."""
    mode   = transport_mode.lower().strip()
    factor = FACTORS.get(mode)
    if factor is None:
        print(f"  WARNING: Unknown mode '{mode}' — recorded as 0 gCO2e")
        return 0.0
    return round(float(distance_km) * factor, 2)


def process_csv(input_path: str) -> list:
    """
    Read a CSV of trip records and return enriched list with co2e_grams.
    Skips rows with missing or invalid fields.
    """
    records = []
    skipped = 0

    with open(input_path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            try:
                distance = float(row["distance_km"])
                if distance < 0:
                    raise ValueError("negative distance")
            except (ValueError, KeyError):
                print(f"  Row {i}: invalid distance '{row.get('distance_km')}' — skipped")
                skipped += 1
                continue

            co2e = calculate_co2e(row["transport_mode"], distance)
            records.append({
                "persona_id":     row["persona_id"],
                "date":           row["date"],
                "transport_mode": row["transport_mode"].lower().strip(),
                "distance_km":    distance,
                "co2e_grams":     co2e,
                "origin":         row.get("origin", ""),
                "destination":    row.get("destination", ""),
            })

    print(f"Processed {len(records)} records ({skipped} skipped)")
    return records


def get_known_modes() -> list:
    return sorted(FACTORS.keys())


if __name__ == "__main__":
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "synthetic_data.csv")
    records = process_csv(path)
    print("\nSample output (first 5 records):")
    for r in records[:5]:
        print(f"  {r['persona_id']:12} | {r['transport_mode']:8} | "
              f"{r['distance_km']:5.1f} km | {r['co2e_grams']:8.1f} gCO2e")
    print(f"\nKnown modes: {get_known_modes()}")
