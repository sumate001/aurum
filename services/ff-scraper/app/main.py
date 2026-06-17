import logging
import os
from datetime import datetime

from flask import Flask, jsonify, request

from .cache import cache_get, cache_set
from .scraper import scrape_calendar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

FILTER_CURRENCIES = [c.strip() for c in os.getenv("FF_FILTER_CURRENCIES", "USD,XAU").split(",")]
FILTER_IMPACT = os.getenv("FF_FILTER_IMPACT", "high")


def _cache_key(start_date: str, currencies: str, impact: str) -> str:
    return f"ff:calendar:{start_date}:{currencies}:{impact}"


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/calendar")
def get_calendar():
    start_date = request.args.get("start_date", datetime.utcnow().strftime("%Y-%m-%d"))
    currencies = request.args.get("currencies", ",".join(FILTER_CURRENCIES))
    impact = request.args.get("impact", FILTER_IMPACT)

    key = _cache_key(start_date, currencies, impact)
    cached = cache_get(key)
    if cached is not None:
        log.info("cache hit key=%s", key)
        return jsonify({"source": "cache", "events": cached})

    log.info("cache miss, scraping FF date=%s", start_date)
    try:
        events = scrape_calendar(start_date)
    except Exception as e:
        log.error("scrape failed: %s", e)
        return jsonify({"error": str(e)}), 502

    currency_list = [c.strip() for c in currencies.split(",")]
    filtered = [
        e for e in events
        if e["currency"] in currency_list and e["impact"] == impact
    ]

    cache_set(key, filtered)
    log.info("scraped %d total, %d filtered", len(events), len(filtered))
    return jsonify({"source": "live", "events": filtered})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
