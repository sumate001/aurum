import yfinance as yf
import pandas as pd
import requests

SYMBOL_MAP = {
    "GOLD#": "GC=F",
    "XAUUSD": "GC=F",
}

TIMEFRAMES = {
    "M15": ("5d", "15m"),
    "H1": ("30d", "1h"),
    "H4": ("90d", "1d"),
}

_SESSION = None


def _get_session():
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        try:
            s.get("https://finance.yahoo.com", timeout=10)
        except Exception:
            pass
        _SESSION = s
    return _SESSION


def fetch_ohlcv(symbol: str) -> dict[str, list[dict]]:
    ticker_sym = SYMBOL_MAP.get(symbol, symbol)
    result: dict[str, list[dict]] = {}

    for tf, (period, interval) in TIMEFRAMES.items():
        try:
            df: pd.DataFrame = yf.download(
                ticker_sym,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                session=_get_session(),
            )
            if df.empty:
                result[tf] = []
                continue

            df = df.rename(columns=str.lower)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = df.index.tz_convert("UTC") if df.index.tz else df.index.tz_localize("UTC")
            df.index = df.index.tz_localize(None)
            records = df[["open", "high", "low", "close", "volume"]].tail(100).reset_index()
            records.columns = ["datetime", "open", "high", "low", "close", "volume"]
            records["datetime"] = records["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            result[tf] = records.to_dict(orient="records")
        except Exception as e:
            result[tf] = []

    return result


def get_current_price(symbol: str) -> float | None:
    ticker_sym = SYMBOL_MAP.get(symbol, symbol)
    try:
        ticker = yf.Ticker(ticker_sym, session=_get_session())
        info = ticker.fast_info
        return float(info.last_price)
    except Exception:
        return None
