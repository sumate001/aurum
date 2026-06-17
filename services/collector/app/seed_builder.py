from datetime import datetime, timezone

from .sources.news import fetch_news
from .sources.banks import fetch_bank_views
from .sources.sentiment import fetch_reddit_sentiment
from .sources.calendar import get_upcoming_events


def build_seed_document(symbol: str, ohlcv: dict, calendar_events: list[dict]) -> tuple[str, dict]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    upcoming = get_upcoming_events(calendar_events)
    news = fetch_news()
    bank_views = fetch_bank_views()
    sentiment = fetch_reddit_sentiment()

    sections = [f"# AURUM Market Intelligence Report\n**Symbol:** {symbol} | **Generated:** {now}\n"]

    # Price snapshot
    h1 = ohlcv.get("H1", [])
    if h1 and isinstance(h1[-1], dict) and "close" in h1[-1]:
        last = h1[-1]
        sections.append(
            f"## Current Price\n- Close: {float(last['close']):.2f}\n"
            f"- High: {float(last['high']):.2f} | Low: {float(last['low']):.2f}\n"
        )

    # Upcoming events
    if upcoming:
        lines = ["## ⚠️ Upcoming High-Impact Events"]
        for ev in upcoming:
            lines.append(
                f"- **{ev['event_name']}** ({ev['currency']}) in {ev['minutes_away']} min"
            )
        sections.append("\n".join(lines) + "\n")

    # News
    if news:
        lines = ["## Recent News"]
        for item in news[:5]:
            if "error" not in item:
                lines.append(f"- [{item['source']}] {item['title']}")
        sections.append("\n".join(lines) + "\n")

    # Bank views
    if bank_views:
        lines = ["## Institutional Views"]
        for bv in bank_views:
            if "headlines" in bv:
                for h in bv["headlines"][:3]:
                    lines.append(f"- [{bv['source']}] {h}")
        sections.append("\n".join(lines) + "\n")

    # Sentiment
    bullish = [p for p in sentiment if isinstance(p, dict) and p.get("upvote_ratio", 0) > 0.7]
    if bullish:
        sections.append(
            f"## Reddit Sentiment\n- {len(bullish)} bullish posts found across gold subreddits\n"
        )

    content = "\n".join(sections)
    sources = {
        "news_count": len([n for n in news if "error" not in n]),
        "bank_sources": len(bank_views),
        "reddit_posts": len(sentiment),
        "upcoming_events": len(upcoming),
    }
    return content, sources
