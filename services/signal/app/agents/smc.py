import pandas as pd
from .base import BaseIndicatorAgent, AgentSignal


class SMCAgent(BaseIndicatorAgent):
    def __init__(self):
        super().__init__("SMC")

    def _detect_bos(self, high: pd.Series, low: pd.Series) -> str:
        if len(high) < 4:
            return "NONE"
        prev_high = float(high.iloc[-3])
        prev_low = float(low.iloc[-3])
        last_high = float(high.iloc[-1])
        last_low = float(low.iloc[-1])

        if last_high > prev_high:
            return "BULLISH"
        if last_low < prev_low:
            return "BEARISH"
        return "NONE"

    def _detect_fvg(self, ohlcv: pd.DataFrame) -> str:
        if len(ohlcv) < 3:
            return "NONE"
        c1_high = float(ohlcv["high"].iloc[-3])
        c3_low = float(ohlcv["low"].iloc[-1])
        c1_low = float(ohlcv["low"].iloc[-3])
        c3_high = float(ohlcv["high"].iloc[-1])

        if c3_low > c1_high:
            return "BULLISH_FVG"
        if c3_high < c1_low:
            return "BEARISH_FVG"
        return "NONE"

    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        high = ohlcv["high"]
        low = ohlcv["low"]
        close = ohlcv["close"]

        bos = self._detect_bos(high, low)
        fvg = self._detect_fvg(ohlcv)
        last_close = float(close.iloc[-1])

        if bos == "BULLISH" or fvg == "BULLISH_FVG":
            sig = "BUY"
        elif bos == "BEARISH" or fvg == "BEARISH_FVG":
            sig = "SELL"
        else:
            sig = "HOLD"

        return AgentSignal(
            agent_name=self.name,
            signal=sig,
            value=last_close,
            metadata={"bos": bos, "fvg": fvg},
        )
