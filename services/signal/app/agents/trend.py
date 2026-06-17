import pandas as pd
from .base import BaseIndicatorAgent, AgentSignal


class TrendAgent(BaseIndicatorAgent):
    def __init__(self):
        super().__init__("TrendEMA")

    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        close = ohlcv["close"]
        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()
        ema200 = close.ewm(span=200).mean()

        last_close = float(close.iloc[-1])
        last_20 = float(ema20.iloc[-1])
        last_50 = float(ema50.iloc[-1])
        last_200 = float(ema200.iloc[-1])

        if last_20 > last_50 > last_200 and last_close > last_20:
            sig, val = "BUY", last_20
        elif last_20 < last_50 < last_200 and last_close < last_20:
            sig, val = "SELL", last_20
        else:
            sig, val = "HOLD", last_20

        return AgentSignal(
            agent_name=self.name,
            signal=sig,
            value=val,
            metadata={"ema20": last_20, "ema50": last_50, "ema200": last_200},
        )
