from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .orchestrator import analyze

app = FastAPI(title="AURUM Signal Engine", version="1.0")


class AnalyzeRequest(BaseModel):
    symbol: str = "GOLD#"
    macro_signal: dict
    ohlcv: dict


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ohlcv")
def get_ohlcv(symbol: str = "GOLD#", tf: str = "H1"):
    from .price import fetch_ohlcv
    all_tf = fetch_ohlcv(symbol)
    return {"symbol": symbol, "tf": tf, "data": all_tf.get(tf, [])}


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    try:
        return analyze(symbol=req.symbol, macro_signal=req.macro_signal, ohlcv=req.ohlcv)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
