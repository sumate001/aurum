from typing import Literal, Optional
from pydantic import BaseModel


class MacroSignalSchema(BaseModel):
    direction: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: int
    recommended_tf: Literal["M15", "H1", "H4", "D1"]
    reasoning: str
    raw_output: dict = {}
