import os
from datetime import datetime, timezone, timedelta

import httpx
from dateutil import parser as dp

FF_SCRAPER_URL        = os.getenv("FF_SCRAPER_URL", "http://aurum-ff-scraper:5000")
PRE_EVENT_WARN_MINUTES = int(os.getenv("FF_PRE_EVENT_WARN_MINUTES", 120))
FF_DAYS_AHEAD         = int(os.getenv("FF_DAYS_AHEAD", 2))

# faireconomy.media — unofficial FF JSON mirror, no auth required
_FAIRECONOMY = {
    "thisweek": "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "nextweek": "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
}
_HIGH_IMPACT_CURRENCIES = {"USD", "XAU"}


def _normalize_faireconomy(events: list[dict]) -> list[dict]:
    """Convert faireconomy.media schema → internal schema."""
    out = []
    for ev in events:
        country = (ev.get("country") or "").upper()
        if country not in _HIGH_IMPACT_CURRENCIES:
            continue
        if (ev.get("impact") or "").lower() != "high":
            continue
        # Parse datetime: date "MM-DD-YYYY" + time "HH:MM" (ET, treat as UTC approx)
        dt = None
        try:
            raw_date = ev.get("date", "")
            raw_time = ev.get("time", "00:00")
            dt = dp.parse(f"{raw_date} {raw_time}").replace(tzinfo=timezone.utc)
        except Exception:
            pass
        out.append({
            "event_datetime": dt.isoformat() if dt else None,
            "currency":       country,
            "impact":         "high",
            "event_name":     ev.get("title", ""),
            "actual":         ev.get("actual") or None,
            "forecast":       ev.get("forecast") or None,
            "previous":       ev.get("previous") or None,
            "surprise_pct":   None,
            "source":         "faireconomy",
        })
    return out


def _fetch_faireconomy_fallback() -> list[dict]:
    """Pull thisweek + nextweek from faireconomy.media."""
    events = []
    for label, url in _FAIRECONOMY.items():
        try:
            resp = httpx.get(url, timeout=15)
            resp.raise_for_status()
            events.extend(_normalize_faireconomy(resp.json()))
        except Exception:
            pass
    return events


def fetch_calendar_events() -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        resp = httpx.get(
            f"{FF_SCRAPER_URL}/api/calendar",
            params={
                "start_date": today,
                "currencies":  "USD,XAU",
                "impact":      "high",
                "days_ahead":  FF_DAYS_AHEAD,
            },
            timeout=20,
        )
        resp.raise_for_status()
        events = resp.json().get("events", [])
        if events:
            return events
        # FF returned empty — try fallback
        raise ValueError("ff-scraper returned empty events")
    except Exception as e:
        fallback = _fetch_faireconomy_fallback()
        if fallback:
            return fallback
        return [{"error": str(e)}]


def get_upcoming_events(events: list[dict], within_minutes: int = PRE_EVENT_WARN_MINUTES) -> list[dict]:
    now    = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=within_minutes)
    upcoming = []
    for ev in events:
        if not ev.get("event_datetime"):
            continue
        try:
            dt = dp.parse(ev["event_datetime"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if now <= dt <= cutoff:
                minutes_away = int((dt - now).total_seconds() / 60)
                upcoming.append({**ev, "minutes_away": minutes_away})
        except Exception:
            pass
    return sorted(upcoming, key=lambda x: x.get("minutes_away", 9999))
