from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CalendarEventSchema(BaseModel):
    event_datetime: datetime
    currency: str
    impact: str
    event_name: str
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    surprise_pct: Optional[float] = None
