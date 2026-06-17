from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel


class AgentOutput(BaseModel):
    agent_name: str
    signal: Literal["BUY", "SELL", "HOLD"]
    value: float
    metadata: dict = {}


class SignalSchema(BaseModel):
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    symbol: str
    broker: str = "XM"
    action: Literal["BUY", "SELL", "HOLD"]
    timeframe: Optional[str] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    confidence: int
    macro_bias: Optional[str] = None
    macro_confidence: Optional[int] = None
    technical_consensus: Optional[str] = None
    reasoning: Optional[str] = None
    upcoming_events: list = []
    status: str = "PENDING_APPROVAL"
    raw_macro: Optional[dict] = None
    raw_technical: Optional[dict] = None
    agent_outputs: list[AgentOutput] = []
