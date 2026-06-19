import pandas as pd
from .base import BaseIndicatorAgent, AgentSignal


class StructureAgent(BaseIndicatorAgent):
    def __init__(self, lookback: int = 50):
        super().__init__("SupportResistance")
        self.lookback = lookback

    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        df = ohlcv.tail(self.lookback)
        close = df["close"]
        high = df["high"]
        low = df["low"]

        resistance = float(high.max())
        support = float(low.min())
        last_close = float(close.iloc[-1])

        range_size = resistance - support
        if range_size == 0:
            return AgentSignal(agent_name=self.name, signal="HOLD", value=last_close,
                               metadata={"support": support, "resistance": resistance})

        position = (last_close - support) / range_size

        if position > 0.85:
            sig = "SELL"   # near resistance
        elif position < 0.15:
            sig = "BUY"    # near support
        elif position > 0.5:
            sig = "BUY"    # upper half of range
        else:
            sig = "SELL"   # lower half of range (bearish territory)

        return AgentSignal(
            agent_name=self.name,
            signal=sig,
            value=last_close,
            metadata={"support": support, "resistance": resistance, "position_pct": round(position * 100, 1)},
        )
