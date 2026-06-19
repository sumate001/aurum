import logging
import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, request

from .cache import cache_get, cache_set
from .scraper import scrape_calendar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

FILTER_CURRENCIES = [c.strip() for c in os.getenv("FF_FILTER_CURRENCIES", "USD,XAU").split(",")]
FILTER_IMPACT     = os.getenv("FF_FILTER_IMPACT", "high")
MAX_DAYS_AHEAD    = 3


def _cache_key(start_date: str, currencies: str, impact: str) -> str:
    return f"ff:calendar:{start_date}:{currencies}:{impact}"


def _scrape_days(start_date: str, days_ahead: int) -> list[dict]:
    """Scrape start_date + up to days_ahead additional days, merging results."""
    all_events: list[dict] = []
    seen: set[str] = set()

    base = datetime.strptime(start_date, "%Y-%m-%d")
    for offset in range(days_ahead + 1):
        day_str = (base + timedelta(days=offset)).strftime("%Y-%m-%d")
        try:
            events = scrape_calendar(day_str)
            for ev in events:
                # deduplicate by (datetime, currency, event_name)
                key = f"{ev.get('event_datetime')}|{ev.get('currency')}|{ev.get('event_name')}"
                if key not in seen:
                    seen.add(key)
                    all_events.append(ev)
            log.info("scraped day=%s got=%d events", day_str, len(events))
        except Exception as e:
            log.warning("scrape failed for day=%s: %s", day_str, e)

    return all_events


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/calendar")
def get_calendar():
    start_date  = request.args.get("start_date", datetime.utcnow().strftime("%Y-%m-%d"))
    currencies  = request.args.get("currencies",  ",".join(FILTER_CURRENCIES))
    impact      = request.args.get("impact",      FILTER_IMPACT)
    days_ahead  = min(int(request.args.get("days_ahead", 2)), MAX_DAYS_AHEAD)

    key = _cache_key(f"{start_date}+{days_ahead}", currencies, impact)
    cached = cache_get(key)
    if cached is not None:
        log.info("cache hit key=%s", key)
        return jsonify({"source": "cache", "events": cached})

    log.info("cache miss, scraping FF start=%s days_ahead=%d", start_date, days_ahead)
    events = _scrape_days(start_date, days_ahead)

    currency_list = [c.strip() for c in currencies.split(",")]
    filtered = [
        e for e in events
        if e["currency"] in currency_list and e["impact"] == impact
    ]

    cache_set(key, filtered)
    log.info("total=%d filtered=%d (currency=%s impact=%s)", len(events), len(filtered), currencies, impact)
    return jsonify({"source": "live", "events": filtered})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
