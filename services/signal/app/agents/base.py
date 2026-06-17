from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal
import pandas as pd


@dataclass
class AgentSignal:
    agent_name: str
    signal: Literal["BUY", "SELL", "HOLD"]
    value: float
    metadata: dict = field(default_factory=dict)


class BaseIndicatorAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def analyze(self, ohlcv: pd.DataFrame) -> AgentSignal:
        """ohlcv columns: open, high, low, close, volume. index: datetime."""
        pass
