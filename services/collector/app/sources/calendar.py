import os
from datetime import datetime, timezone, timedelta

import httpx

FF_SCRAPER_URL = os.getenv("FF_SCRAPER_URL", "http://aurum-ff-scraper:5000")
PRE_EVENT_WARN_MINUTES = int(os.getenv("FF_PRE_EVENT_WARN_MINUTES", 120))


def fetch_calendar_events() -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        resp = httpx.get(
            f"{FF_SCRAPER_URL}/api/calendar",
            params={"start_date": today, "currencies": "USD,XAU", "impact": "high"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception as e:
        return [{"error": str(e)}]


def get_upcoming_events(events: list[dict], within_minutes: int = PRE_EVENT_WARN_MINUTES) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=within_minutes)
    upcoming = []
    for ev in events:
        if not ev.get("event_datetime"):
            continue
        try:
            from dateutil import parser as dp
            dt = dp.parse(ev["event_datetime"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if now <= dt <= cutoff:
                minutes_away = int((dt - now).total_seconds() / 60)
                upcoming.append({**ev, "minutes_away": minutes_away})
        except Exception:
            pass
    return sorted(upcoming, key=lambda x: x.get("minutes_away", 9999))
