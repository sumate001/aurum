from datetime import datetime, timezone

import pandas as pd

from .sources.news import fetch_news
from .sources.banks import fetch_bank_views
from .sources.sentiment import fetch_reddit_sentiment
from .sources.calendar import get_upcoming_events
from .sources.cftc import fetch_cftc_positioning, format_for_seed as cftc_format


def _technical_price_context(ohlcv: dict) -> str:
    """Build a technical summary section so MiroFish agents can reason about overextension and momentum."""
    lines = []

    # H1: momentum over last 4 and 24 bars
    valid_h1 = [b for b in ohlcv.get("H1", [])
                if isinstance(b, dict) and "close" in b and "error" not in b]
    if len(valid_h1) >= 5:
        try:
            closes = [float(b["close"]) for b in valid_h1]
            highs  = [float(b["high"])  for b in valid_h1]
            lows   = [float(b["low"])   for b in valid_h1]

            chg_4h  = (closes[-1] - closes[-4])  / closes[-4]  * 100
            chg_24h = (closes[-1] - closes[-24]) / closes[-24] * 100 if len(closes) >= 24 else None

            lines.append(f"- 4H price change : {chg_4h:+.2f}%")
            if chg_24h is not None:
                lines.append(f"- 24H price change: {chg_24h:+.2f}%")

            # Spike/crash warning
            if abs(chg_4h) > 0.8:
                word = "ขึ้นแรงผิดปกติ" if chg_4h > 0 else "ลงแรงผิดปกติ"
                lines.append(
                    f"  ⚠️ ALERT: ราคา{word} {abs(chg_4h):.2f}% ใน 4H — "
                    f"{'ระวัง reversal/sell pressure' if chg_4h > 0 else 'ระวัง bounce/buy pressure'}"
                )

            # High volatility range
            spike_range_pct = (max(highs[-4:]) - min(lows[-4:])) / closes[-4] * 100
            if spike_range_pct > 1.5:
                lines.append(
                    f"  ⚠️ High volatility: H-L range {spike_range_pct:.1f}% ใน 4H "
                    f"— likely news/event driven move"
                )
        except (ValueError, IndexError, ZeroDivisionError):
            pass

    # H4: EMA200 distance and RSI overextension
    valid_h4 = [b for b in ohlcv.get("H4", [])
                if isinstance(b, dict) and "close" in b and "error" not in b]
    if len(valid_h4) >= 20:
        try:
            series = pd.Series([float(b["close"]) for b in valid_h4])
            span   = min(200, len(series))
            ema200 = float(series.ewm(span=span).mean().iloc[-1])
            last   = float(series.iloc[-1])
            dist_pct = (last - ema200) / ema200 * 100

            if abs(dist_pct) > 1.5:
                pos      = "สูงกว่า" if dist_pct > 0 else "ต่ำกว่า"
                pressure = "sell pressure / overbought risk" if dist_pct > 0 else "buy pressure / oversold opportunity"
                lines.append(f"- ราคาอยู่ {pos} EMA{span}(H4) = {abs(dist_pct):.1f}% → {pressure}")
            else:
                lines.append(f"- ราคาอยู่ใกล้ EMA{span}(H4) ±{abs(dist_pct):.1f}% — neutral zone")

            # RSI H4
            delta = series.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rsi   = float((100 - 100 / (1 + gain / loss.replace(0, 1e-9))).iloc[-1])
            if rsi > 70:
                lines.append(f"  ⚠️ H4 RSI {rsi:.0f} — overbought territory, high reversal risk")
            elif rsi < 30:
                lines.append(f"  ⚠️ H4 RSI {rsi:.0f} — oversold territory, high bounce risk")
            else:
                lines.append(f"- H4 RSI: {rsi:.0f} (neutral)")
        except (ValueError, IndexError, ZeroDivisionError):
            pass

    if not lines:
        return ""
    return "## Technical Price Context\n" + "\n".join(lines) + "\n"


def build_seed_document(symbol: str, ohlcv: dict, calendar_events: list[dict]) -> tuple[str, dict]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    upcoming = get_upcoming_events(calendar_events)
    news = fetch_news()
    bank_views = fetch_bank_views()
    sentiment = fetch_reddit_sentiment()
    cftc = fetch_cftc_positioning()

    sections = [f"# AURUM Market Intelligence Report\n**Symbol:** {symbol} | **Generated:** {now}\n"]

    # Price snapshot
    h1 = ohlcv.get("H1", [])
    if h1 and isinstance(h1[-1], dict) and "close" in h1[-1]:
        last = h1[-1]
        sections.append(
            f"## Current Price\n- Close: {float(last['close']):.2f}\n"
            f"- High: {float(last['high']):.2f} | Low: {float(last['low']):.2f}\n"
        )

    # Technical context for macro agents
    tech_ctx = _technical_price_context(ohlcv)
    if tech_ctx:
        sections.append(tech_ctx)

    # Upcoming events
    if upcoming:
        lines = ["## ⚠️ Upcoming High-Impact Events"]
        for ev in upcoming:
            lines.append(
                f"- **{ev['event_name']}** ({ev['currency']}) in {ev['minutes_away']} min"
            )
        sections.append("\n".join(lines) + "\n")

    # CFTC COT positioning
    cftc_section = cftc_format(cftc)
    if cftc_section:
        sections.append(cftc_section)

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
        "news_count":     len([n for n in news if "error" not in n]),
        "bank_sources":   len(bank_views),
        "reddit_posts":   len(sentiment),
        "upcoming_events": len(upcoming),
        "cftc_ok":        "error" not in cftc,
    }
    return content, sources
