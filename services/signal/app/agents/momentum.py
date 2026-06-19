import pandas as pd
from .base import BaseIndicatorAgent, AgentSignal


class MomentumAgent(BaseIndicatorAgent):
    def __init__(self):
        super().__init__("MomentumRSI")

    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        close = ohlcv["close"]
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi = 100 - (100 / (1 + rs))

        val = float(rsi.iloc[-1])
        if val < 40:
            sig = "BUY"
        elif val > 60:
            sig = "SELL"
        else:
            sig = "HOLD"

        return AgentSignal(agent_name=self.name, signal=sig, value=val, metadata={"rsi14": val})
