import pandas as pd
from .base import BaseIndicatorAgent, AgentSignal


class VolumeAgent(BaseIndicatorAgent):
    def __init__(self):
        super().__init__("VolumeVWAP")

    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        close = ohlcv["close"]
        high = ohlcv["high"]
        low = ohlcv["low"]
        volume = ohlcv["volume"]

        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum().replace(0, 1)

        last_close = float(close.iloc[-1])
        last_vwap = float(vwap.iloc[-1])
        avg_vol = float(volume.rolling(20).mean().iloc[-1])
        last_vol = float(volume.iloc[-1])

        vol_surge = last_vol > avg_vol * 1.2

        if last_close > last_vwap and vol_surge:
            sig = "BUY"
        elif last_close < last_vwap and vol_surge:
            sig = "SELL"
        else:
            sig = "HOLD"

        return AgentSignal(
            agent_name=self.name,
            signal=sig,
            value=last_vwap,
            metadata={"vwap": last_vwap, "vol_surge": vol_surge, "vol_ratio": round(last_vol / avg_vol, 2) if avg_vol else 0},
        )
