import feedparser
from datetime import datetime, timezone

FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.fxstreet.com/rss/news",
    "https://www.kitco.com/rss/Lo-gold-news.rss",
    "https://news.kitco.com/rss/",
]

GOLD_KEYWORDS = ["gold", "xau", "precious metal", "bullion", "fed", "dollar", "inflation", "comex", "spot gold", "kitco"]


def fetch_news() -> list[dict]:
    articles = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                text = f"{title} {summary}".lower()
                if not any(kw in text for kw in GOLD_KEYWORDS):
                    continue
                articles.append({
                    "source": feed.feed.get("title", url),
                    "title": title,
                    "summary": summary,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                })
        except Exception as e:
            articles.append({"source": url, "error": str(e)})
    return articles
