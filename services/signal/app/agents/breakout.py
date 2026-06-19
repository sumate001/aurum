import pandas as pd
from .base import BaseIndicatorAgent, AgentSignal


class BreakoutAgent(BaseIndicatorAgent):
    def __init__(self, period: int = 20):
        super().__init__("BreakoutDonchian")
        self.period = period

    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        high = ohlcv["high"]
        low = ohlcv["low"]
        close = ohlcv["close"]

        upper = high.rolling(self.period).max()
        lower = low.rolling(self.period).min()

        last_close = float(close.iloc[-1])
        last_upper = float(upper.iloc[-1])
        last_lower = float(lower.iloc[-1])
        mid = (last_upper + last_lower) / 2
        channel_range = last_upper - last_lower if last_upper > last_lower else 1.0

        # Fire when price is in the top/bottom 15% of the Donchian channel
        position = (last_close - last_lower) / channel_range
        if position >= 0.85:
            sig = "BUY"
        elif position <= 0.15:
            sig = "SELL"
        else:
            sig = "HOLD"

        return AgentSignal(
            agent_name=self.name,
            signal=sig,
            value=last_close,
            metadata={"upper": last_upper, "lower": last_lower, "mid": mid},
        )
