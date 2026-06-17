import requests
from bs4 import BeautifulSoup

SOURCES = [
    {
        "name": "Goldman Sachs Insights",
        "url": "https://www.goldmansachs.com/insights/",
        "selector": "h3",
        "keywords": ["gold", "commodity", "inflation", "fed", "rates"],
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def fetch_bank_views() -> list[dict]:
    results = []
    for src in SOURCES:
        try:
            resp = requests.get(src["url"], headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            headlines = [el.get_text(strip=True) for el in soup.select(src["selector"])[:20]]
            filtered = [
                h for h in headlines
                if any(kw in h.lower() for kw in src["keywords"])
            ]
            results.append({"source": src["name"], "headlines": filtered[:5]})
        except Exception as e:
            results.append({"source": src["name"], "error": str(e)})
    return results
