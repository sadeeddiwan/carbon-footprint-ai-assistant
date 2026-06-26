# carbon-footprint-ai-assistant
PROJECT: Carbon Footprint AI Assistant — University BIP Project, Hochschule Heilbronn, team of 5 students.
WHAT IT DOES: A fully automated agentic AI pipeline that reads weekly transport data per persona, calculates CO₂ emissions using official factors, routes through a two-branch decision system, runs an AI agent that autonomously investigates the data, and delivers personalised weekly briefings to a Matrix/Element chat room — one briefing per persona, no manual steps.
TECH STACK:

n8n (self-hosted via Docker) — 12-node visual workflow orchestrator, runs locally on laptop
Python — deterministic emissions calculation using DEFRA 2023 factors, verified and auditable
Ollama + Mistral 7B — local LLM, no external API, no data leaves the laptop
Matrix/Element — open-source GDPR-compliant messaging protocol for briefing delivery
Synthetic CSV dataset — 293 records, 6 personas, 4 weeks, 6 transport modes (car, train, bus, bicycle, walking, subway), designed with realistic week-to-week behavioural variation

PIPELINE (12 nodes):

Manual Trigger → Read CSV → Calculate Emissions → Aggregate by Week (per persona) → Switch (2 branches) → Set Context → Merge → ReAct Agent → IF Alert → Format Message → Merge → Send to Matrix
TWO BRANCHES:

Critical branch (⚠️): triggers when emissions increase more than 10% week-on-week → urgent tone, alert header, priority actions
Standard branch (🌍): everything else (stable, decreasing, first week) → balanced tone, normal briefing

THREE PERSONAS — each receives their own personalised briefing:
PersonaProfileNormal weekSpike weekBranchcar_001Urban car commuter18,117 gCO₂e25,619 gCO₂e (+42%)⚠️ Criticalhyb_001Hybrid commuter (train + car + bus)13,176 gCO₂e20,951 gCO₂e (+59%)⚠️ Criticalpt_001Public transport user (train + subway)8,950 gCO₂estable🌍 Standard
REACT AGENT: The AI does not receive pre-computed answers. It autonomously calls three tools — get_weekly_summary(), get_top_trips(), compare_weeks() — in a Think→Act→Observe loop, deciding what to investigate before writing recommendations. The system enforces that at least 2 tool calls must be made before recommendations are accepted. If Ollama times out, a grounded deterministic fallback generates recommendations using real numbers from the data — the pipeline never fails silently.
MODE-AWARE RECOMMENDATIONS: The agent knows the emission factor of every transport mode (car: 170, train: 35.7, subway: 27.3, bicycle: 0 gCO₂e/km). It never tells a public transport user to reduce train journeys. For pt_001 it correctly recommends replacing the subway leg with cycling to save 218 gCO₂e per trip — the only genuine improvement available to an already sustainable commuter.
VERIFIED SAMPLE OUTPUTS:
Critical alert (car_001, spike week):

"⚠️ EMISSIONS ALERT — CAR 001 — Week 3. Emissions rose 42%. Total: 25,619 gCO₂e. Car: 100%. Highest trip: 14.2km car → 2,414 gCO₂e. Switching to train saves 1,906 gCO₂e on that single journey."

Standard briefing (pt_001, normal week):

"🌍 Weekly Briefing — PT 001 — Week 5. Total: 8,950 gCO₂e. Stable (+0.2%). Main source: Train (88%). Your transport mix is already sustainable. Consider replacing the 4km subway leg with cycling — saves 218 gCO₂e per trip at zero emissions."

DEMO FLOW:

Pre-load 3 weeks per persona in Element showing the full story (normal → spike → recovery)
Point out car_001 and hyb_001 both have ⚠️ alert messages during spike weeks
Point out pt_001 consistently shows 🌍 Standard — already sustainable
Trigger live run in n8n → watch 12 nodes execute one by one
Week 4 briefing for selected persona arrives in Element live
Click ReAct Agent node → show reasoning_trace in JSON output panel as proof of autonomous tool investigation

KEY TALKING POINTS:

All inference runs locally — no data sent to any external server
Every CO₂ number traces to a specific DEFRA 2023 factor (fully auditable)
The AI decides what to investigate — the sequence is not hardcoded
The system makes a routing decision (Critical vs Standard) based on what it finds in the data
Three different personas produce three completely different emission profiles and recommendation styles
The substitution test: you cannot replace the ReAct agent with a text template because a template cannot call tools, read the results, and decide what to investigate next
Even when Ollama is slow, the grounded fallback produces accurate data-driven recommendations — the pipeline never outputs invented numbers

LIMITATIONS ACKNOWLEDGED:

Synthetic data — real data collection requires GDPR consent infrastructure and ethics approval, out of scope for a 4-week project
DEFRA UK factors used — production would use German Umweltbundesamt (UBA) factors; the calculator is factor-agnostic, one JSON file swap required
Mistral 7B sometimes completes tool calls slowly and falls back to deterministic recommendations — a larger model would be more reliable
Three representative personas shown in demo — full system supports all 6 in the dataset

FUTURE WORK: Real data collection via Google Forms or Google Maps Timeline API, per-user private Matrix rooms, LangGraph for multi-week agent memory, natural language trip input ("took an Uber to the station"), mobile app for trip logging.
