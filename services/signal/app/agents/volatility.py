import pandas as pd
from .base import BaseIndicatorAgent, AgentSignal


class VolatilityAgent(BaseIndicatorAgent):
    def __init__(self):
        super().__init__("VolatilityATR")

    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        high = ohlcv["high"]
        low = ohlcv["low"]
        close = ohlcv["close"]

        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])

        # High ATR = high volatility → HOLD to avoid false breakouts
        avg_price = float(close.mean())
        atr_pct = atr / avg_price * 100

        if atr_pct > 1.5:
            sig = "HOLD"
        elif atr_pct < 0.3:
            sig = "HOLD"
        else:
            sig = "BUY"  # normal volatility is favorable

        return AgentSignal(
            agent_name=self.name,
            signal=sig,
            value=atr,
            metadata={"atr14": atr, "atr_pct": round(atr_pct, 3)},
        )
