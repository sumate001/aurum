import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

FF_URL = "https://www.forexfactory.com/calendar"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
NY_TZ = ZoneInfo("America/New_York")


def _parse_impact(row) -> str:
    impact_cell = row.find("td", class_="calendar__impact")
    if not impact_cell:
        return "low"
    span = impact_cell.find("span")
    if not span:
        return "low"
    cls = " ".join(span.get("class", []))
    if "high" in cls:
        return "high"
    if "medium" in cls:
        return "medium"
    return "low"


def scrape_calendar(start_date: str | None = None) -> list[dict]:
    params = {}
    if start_date:
        params["day"] = start_date

    resp = requests.get(FF_URL, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", class_="calendar__table")
    if not table:
        return []

    events = []
    current_date_str = start_date or datetime.now(NY_TZ).strftime("%Y-%m-%d")

    for row in table.find_all("tr", class_=re.compile(r"calendar__row")):
        date_cell = row.find("td", class_="calendar__date")
        if date_cell and date_cell.get_text(strip=True):
            date_text = date_cell.get_text(strip=True)
            try:
                parsed = dateparser.parse(date_text)
                if parsed:
                    current_date_str = parsed.strftime("%Y-%m-%d")
            except Exception:
                pass

        time_cell = row.find("td", class_="calendar__time")
        currency_cell = row.find("td", class_="calendar__currency")
        event_cell = row.find("td", class_="calendar__event")
        actual_cell = row.find("td", class_="calendar__actual")
        forecast_cell = row.find("td", class_="calendar__forecast")
        previous_cell = row.find("td", class_="calendar__previous")

        if not (currency_cell and event_cell):
            continue

        currency = currency_cell.get_text(strip=True)
        event_name = event_cell.get_text(strip=True)
        impact = _parse_impact(row)

        time_str = time_cell.get_text(strip=True) if time_cell else ""
        try:
            dt_naive = dateparser.parse(f"{current_date_str} {time_str}")
            if dt_naive:
                dt = dt_naive.replace(tzinfo=NY_TZ).astimezone(timezone.utc)
            else:
                dt = None
        except Exception:
            dt = None

        actual = actual_cell.get_text(strip=True) if actual_cell else None
        forecast = forecast_cell.get_text(strip=True) if forecast_cell else None
        previous = previous_cell.get_text(strip=True) if previous_cell else None

        surprise_pct = None
        if actual and forecast:
            try:
                a = float(re.sub(r"[^0-9.\-]", "", actual))
                f = float(re.sub(r"[^0-9.\-]", "", forecast))
                if f != 0:
                    surprise_pct = round((a - f) / abs(f) * 100, 2)
            except Exception:
                pass

        events.append({
            "event_datetime": dt.isoformat() if dt else None,
            "currency": currency,
            "impact": impact,
            "event_name": event_name,
            "actual": actual or None,
            "forecast": forecast or None,
            "previous": previous or None,
            "surprise_pct": surprise_pct,
        })

    return events
