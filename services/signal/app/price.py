import yfinance as yf
import pandas as pd

SYMBOL_MAP = {"GOLD#": "GC=F", "XAUUSD": "GC=F"}

TIMEFRAMES = {
    "M15": ("5d",  "15m"),
    "M30": ("10d", "30m"),
    "H1":  ("30d", "1h"),
    "H4":  ("90d", "1d"),
}


def fetch_ohlcv(symbol: str) -> dict[str, list[dict]]:
    ticker_sym = SYMBOL_MAP.get(symbol, symbol)
    result: dict[str, list[dict]] = {}

    for tf, (period, interval) in TIMEFRAMES.items():
        try:
            df = yf.download(
                ticker_sym, period=period, interval=interval,
                progress=False, auto_adjust=True,
            )
            if df.empty:
                result[tf] = []
                continue
            df = df.rename(columns=str.lower)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            # tz_convert(None) converts to UTC then drops tz label — append Z so
            # JavaScript parses as UTC, not browser local time
            df.index = df.index.tz_convert("UTC") if df.index.tz else df.index.tz_localize("UTC")
            df.index = df.index.tz_localize(None)
            records = df[["open", "high", "low", "close", "volume"]].tail(120).reset_index()
            records.columns = ["datetime", "open", "high", "low", "close", "volume"]
            records["datetime"] = records["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            result[tf] = records.to_dict(orient="records")
        except Exception:
            result[tf] = []

    return result
