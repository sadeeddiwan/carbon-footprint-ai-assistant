"""
Matrix Message Delivery — Carbon Footprint AI Assistant
Sends weekly briefings to a Matrix/Element room via the Client-Server API.

Setup (do this once before running):
  1. Create a bot account at https://app.element.io
  2. Get the bot's access token (Settings → Help & About → Access Token)
  3. Create a private room (E2EE OFF), invite the bot
  4. Get the room ID (Room Settings → Advanced → Internal room ID)
  5. Set MATRIX_TOKEN and MATRIX_ROOM as environment variables
     OR edit ACCESS_TOKEN and ROOM_ID below directly

Test:
  python scripts/matrix_sender.py
  → Check Element for the test message
"""

import requests
import time
import os

# ── Credentials ─────────────────────────────────────────────────────────────
# Set via environment variables OR replace the placeholder strings below.
HOMESERVER   = "https://matrix.org"
ACCESS_TOKEN = "mat_TP075GjrIAjNM0tlxGBZbJNyQhtAK6_WETnt1"
ROOM_ID      = "!rERJxNpahAKkrNMlfT:matrix.org"
REQUEST_TIMEOUT = 20


# ── Core send function ───────────────────────────────────────────────────────
def send_message(text: str) -> dict:
    """
    Send a plain-text message to the configured Matrix room.

    Each message needs a unique transaction ID to prevent duplicates
    if the request is retried. We use millisecond timestamp for this.

    Returns the API response dict (contains 'event_id' on success).
    Raises requests.HTTPError on failure.
    """
    if "YOUR_BOT_TOKEN" in ACCESS_TOKEN:
        raise ValueError(
            "ACCESS_TOKEN is not set. "
            "Set the MATRIX_TOKEN environment variable or edit matrix_sender.py."
        )
    if "YOUR_ROOM_ID" in ROOM_ID:
        raise ValueError(
            "ROOM_ID is not set. "
            "Set the MATRIX_ROOM environment variable or edit matrix_sender.py."
        )

    txn_id  = str(int(time.time() * 1000))
    url     = (f"{HOMESERVER}/_matrix/client/v3/rooms/{ROOM_ID}"
               f"/send/m.room.message/{txn_id}")
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type":  "application/json",
    }
    body = {"msgtype": "m.text", "body": text}

    response = requests.put(url, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    event_id = response.json().get("event_id", "unknown")
    print(f"✓ Message sent — event_id: {event_id}")
    return response.json()


# ── Message formatter ────────────────────────────────────────────────────────
def format_briefing(data: dict) -> str:
    """
    Build the full formatted briefing message from the agent's output dict.
    data must contain: week, total_co2e, dominant_mode, dominant_pct,
                       trend, change_pct, prev_total, recommendations,
                       alert_mode
    """
    week      = data["week"]
    total     = data["total_co2e"]
    dominant  = data["dominant_mode"].replace("_", " ").title()
    dom_pct   = data["dominant_pct"]
    trend     = data["trend"]
    change    = data["change_pct"]
    prev      = data.get("prev_total")
    recs      = data["recommendations"]
    is_alert  = data.get("alert_mode", False)

    # Trend line
    if trend == "first week":
        trend_line = "First week — baseline established."
    elif trend == "increasing":
        prev_str   = f"{prev:,.0f} gCO₂e" if prev else "N/A"
        trend_line = f"▲ Up {change}% from last week  (prev: {prev_str})"
    elif trend == "decreasing":
        prev_str   = f"{prev:,.0f} gCO₂e" if prev else "N/A"
        trend_line = f"▼ Down {abs(change)}% from last week  (prev: {prev_str})"
    else:
        sign       = "+" if change >= 0 else ""
        trend_line = f"→ Stable vs last week  ({sign}{change}%)"

    if is_alert:
        return (
            f"⚠️ EMISSIONS ALERT — Week {week}\n\n"
            f"Emissions rose {change}% this week — action recommended.\n\n"
            f"Total:       {total:,.0f} gCO₂e\n"
            f"{trend_line}\n"
            f"Main source: {dominant} ({dom_pct}% of emissions)\n\n"
            f"📋 Priority Actions:\n\n"
            f"{recs}\n\n"
            f"— Carbon Footprint AI Assistant | DEFRA 2023 factors"
        )
    else:
        return (
            f"🌍 Weekly Carbon Briefing — Week {week}\n\n"
            f"Total: {total:,.0f} gCO₂e\n"
            f"{trend_line}\n"
            f"Main source: {dominant} ({dom_pct}% of emissions)\n\n"
            f"📋 Recommendations:\n\n"
            f"{recs}\n\n"
            f"— Carbon Footprint AI Assistant | DEFRA 2023 factors"
        )


# ── Manual test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from datetime import datetime

    print("Sending test message to Matrix room...")
    print(f"  Homeserver: {HOMESERVER}")
    print(f"  Room ID:    {ROOM_ID}\n")

    test_msg = (
        f"✅ Carbon Footprint Bot — connection test\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"If you see this in Element, Matrix integration is working."
    )

    try:
        result = send_message(test_msg)
        print("\n✅ SUCCESS — check Element for the test message.")
    except ValueError as e:
        print(f"\n❌ CONFIGURATION ERROR: {e}")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        body = e.response.text if e.response else ""
        print(f"\n❌ MATRIX API ERROR  {code}: {body}")
        FIXES = {
            401: "Access token is wrong — re-copy from Element → Settings → Help & About → Access Token",
            403: "Bot is not in the room — invite @your-bot:matrix.org in Element",
            400: "Room ID is wrong — must start with ! and end with :matrix.org",
        }
        if e.response:
            print(f"   Fix: {FIXES.get(e.response.status_code, 'Check credentials and try again')}")
