"""
ReAct Agent — Carbon Footprint AI Assistant
Autonomous investigation: decides what tools to call and in what order.

Run standalone:   python scripts/react_agent.py
Used by n8n:      the JavaScript version in Node 8 is identical logic.

Output:
  - Reasoning steps → stderr (visible in terminal)
  - Final JSON result → stdout (captured by n8n)
"""

import requests
import json
import re
import sys
import os

# ── Configuration ──────────────────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL      = "mistral"
MAX_STEPS  = 6
CSV_PATH   = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "data", "synthetic_data.csv")

# ── Bootstrap pipeline dependencies ────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emissions_calculator import process_csv
from aggregate import aggregate, get_week, determine_branch

# ── Load data once ─────────────────────────────────────────────────────────────
records   = process_csv(CSV_PATH)
summaries = aggregate(records)
target    = summaries[-1]   # Most recent week


# ── Tool definitions ────────────────────────────────────────────────────────────
def get_weekly_summary(week_number):
    """Return total CO2e and mode breakdown for a given week."""
    w = [r for r in records if get_week(r["date"]) == int(week_number)]
    if not w:
        return {"error": f"No data found for week {week_number}"}
    by_mode, total = {}, 0.0
    for r in w:
        total += r["co2e_grams"]
        by_mode[r["transport_mode"]] = by_mode.get(r["transport_mode"], 0.0) + r["co2e_grams"]
    dom = max(by_mode, key=by_mode.get)
    return {
        "week":          week_number,
        "total_co2e":    round(total, 1),
        "by_mode":       {k: round(v, 1) for k, v in
                          sorted(by_mode.items(), key=lambda x: x[1], reverse=True)},
        "dominant_mode": dom,
        "dominant_pct":  round(by_mode[dom] / total * 100),
    }


def get_top_trips(week_number, n=3):
    """Return the N highest-emission individual trips in a given week."""
    w = [r for r in records if get_week(r["date"]) == int(week_number)]
    if not w:
        return {"error": f"No data for week {week_number}"}
    top = sorted(w, key=lambda r: r["co2e_grams"], reverse=True)[:int(n)]
    return {"top_trips": [{
        "persona":    t["persona_id"],
        "date":       t["date"],
        "mode":       t["transport_mode"],
        "distance_km": t["distance_km"],
        "co2e_grams": t["co2e_grams"],
    } for t in top]}


def compare_weeks(week1, week2):
    """Compare total emissions between two weeks."""
    s1 = get_weekly_summary(week1)
    s2 = get_weekly_summary(week2)
    if "error" in s1 or "error" in s2:
        return {"error": "One or both weeks not found"}
    diff = s2["total_co2e"] - s1["total_co2e"]
    pct  = round(diff / s1["total_co2e"] * 100, 1) if s1["total_co2e"] > 0 else 0
    return {
        "week1":              {"week": week1, "total": s1["total_co2e"]},
        "week2":              {"week": week2, "total": s2["total_co2e"]},
        "difference_gco2e":   round(diff, 1),
        "change_pct":         pct,
        "trend":              "increasing" if pct > 5 else "decreasing" if pct < -5 else "stable",
    }


TOOLS = {
    "get_weekly_summary": get_weekly_summary,
    "get_top_trips":      get_top_trips,
    "compare_weeks":      compare_weeks,
}


# ── Action parser ───────────────────────────────────────────────────────────────
def parse_action(text):
    """Extract tool name and args from 'Action: tool_name(arg1, arg2)'."""
    m = re.search(r"Action:\s*(\w+)\(([^)]*)\)", text)
    if not m:
        return None, None
    name = m.group(1).strip()
    args = []
    for part in m.group(2).split(","):
        part = part.strip()
        try:
            args.append(int(part) if "." not in part else float(part))
        except ValueError:
            args.append(part.strip("'\""))
    return name, args


# ── Determine context from branch ──────────────────────────────────────────────
branch     = determine_branch(target)
alert_mode = branch == "critical"
tone       = "urgent" if alert_mode else "informative"

CONTEXT_NOTE = {
    "urgent":      "Emissions increased significantly this week. Prioritise the single most impactful action the user can take immediately.",
    "informative": "Emissions are within normal range. Provide balanced, practical recommendations.",
}[tone]

TONE_GUIDE = {
    "urgent":      "Lead with the highest-impact action. Be direct and specific. Reference exact CO2e numbers.",
    "informative": "Be balanced and practical. Focus on achievable behaviour changes. Acknowledge what is already working.",
}[tone]


# ── System prompt ───────────────────────────────────────────────────────────────
SYSTEM = f"""You are a carbon footprint analysis agent investigating Week {target['week']} transport data.

CONTEXT: {CONTEXT_NOTE}
TONE: {TONE_GUIDE}

AVAILABLE TOOLS:
- get_weekly_summary(week_number)   — total CO2e and mode breakdown for a week
- get_top_trips(week_number, n)     — the N highest-emission individual trips
- compare_weeks(week1, week2)       — compare total emissions between two weeks

Use this exact format for each investigation step:
Thought: [your reasoning about what to look at next]
Action: tool_name(argument1, argument2)

Investigate at least 2 different aspects before writing recommendations.
When you have enough information, write:

FINAL RECOMMENDATIONS:
1. [specific recommendation referencing actual numbers from your investigation]
2. [specific recommendation referencing actual numbers]
3. [specific recommendation referencing actual numbers]

Output ONLY the investigation steps and the final recommendations. No introduction."""


# ── ReAct loop ──────────────────────────────────────────────────────────────────
def run_agent():
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": f"Investigate Week {target['week']} transport emissions now."}
    ]

    print(f"\n{'='*58}", file=sys.stderr)
    print(f"  REACT AGENT  |  Week {target['week']}  |  Branch: {branch.upper()}", file=sys.stderr)
    print(f"  Tone: {tone.upper()}", file=sys.stderr)
    print(f"{'='*58}\n", file=sys.stderr)

    final_recs = None
    trace      = []

    for step in range(MAX_STEPS):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model":    MODEL,
                    "messages": messages,
                    "stream":   False,
                    "options":  {"temperature": 0.3, "num_predict": 500},
                },
                timeout=500,
            )
            resp.raise_for_status()
            text = resp.json()["message"]["content"].strip()
        except requests.ConnectionError:
            print(f"\n[ERROR] Cannot reach Ollama at {OLLAMA_URL}", file=sys.stderr)
            print("[ERROR] Make sure Ollama is running: ollama serve", file=sys.stderr)
            break
        except Exception as e:
            print(f"\n[ERROR] Ollama call failed: {e}", file=sys.stderr)
            break

        print(f"--- Step {step + 1} ---", file=sys.stderr)
        print(text, file=sys.stderr)
        print(file=sys.stderr)

        trace.append(f"--- Step {step + 1} ---\n{text}")

        # Check if the agent finished
        if "FINAL RECOMMENDATIONS:" in text.upper():
            idx        = text.upper().find("FINAL RECOMMENDATIONS:")
            final_recs = text[idx + len("FINAL RECOMMENDATIONS:"):].strip()
            break

        # Parse and execute tool call
        tool_name, args = parse_action(text)
        if tool_name and tool_name in TOOLS:
            try:
                observation = json.dumps(TOOLS[tool_name](*args), indent=2)
            except Exception as e:
                observation = json.dumps({"error": str(e)})
            print(f"[TOOL CALLED: {tool_name}({args})]", file=sys.stderr)
            print(f"Observation: {observation}\n", file=sys.stderr)
        else:
            observation = "No valid tool call found. Use: Action: tool_name(args)"

        messages.append({"role": "assistant", "content": text})
        messages.append({
            "role":    "user",
            "content": f"Observation: {observation}\n\nContinue investigating or write FINAL RECOMMENDATIONS.",
        })

    # Fallback if agent did not complete
    if not final_recs:
        if alert_mode:
            final_recs = (
                "1. Emissions spiked significantly this week — identify your highest-emission "
                "day and replace the car journey with train to make the biggest single impact.\n"
                "2. Check which trips exceeded 30km by car — these are your most impactful "
                "reduction targets. The regional train produces 80% fewer emissions on long routes.\n"
                "3. Consider a car-sharing arrangement for recurring long commutes to halve "
                "per-person emissions immediately."
            )
        else:
            final_recs = (
                "1. Replace two weekly car commutes with public transport — this alone "
                "could reduce emissions by approximately 30%.\n"
                "2. Your longest car journeys produce the most CO2e per trip — consider "
                "the regional train for routes over 20km.\n"
                "3. Your existing public transport days are working well — protect this "
                "habit even during busy weeks."
            )
        print("[FALLBACK] Using pre-written recommendations (Ollama did not complete)", file=sys.stderr)

    # Build result object
    result = {
        **target,
        "recommendations":  final_recs,
        "reasoning_trace":  "\n\n".join(trace),
        "alert_mode":       alert_mode,
        "tone":             tone,
        "branch":           branch,
    }

    print(json.dumps(result))   # stdout → captured by n8n
    return result


if __name__ == "__main__":
    run_agent()
