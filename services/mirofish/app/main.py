from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .simulation import _run_simulation_async
from .report import parse_to_macro_signal

app = FastAPI(title="AURUM MiroFish", version="1.0")


class SimulateRequest(BaseModel):
    seed_document: str
    symbol: str = "GOLD#"
    upcoming_events: list = []
    simulation_rounds: int = 3


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/simulate")
async def simulate(req: SimulateRequest):
    try:
        result = await _run_simulation_async(
            seed_document=req.seed_document,
            symbol=req.symbol,
            upcoming_events=req.upcoming_events,
            rounds=req.simulation_rounds,
        )
        return parse_to_macro_signal(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
