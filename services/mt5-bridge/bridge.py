"""
MT5 Bridge — runs on Windows only (MetaTrader5 package requires Windows + MT5 terminal).
Start with: uvicorn bridge:app --host 0.0.0.0 --port 8400
"""
import os
import time
import logging
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

log = logging.getLogger(__name__)

API_KEY = os.getenv("MT5_BRIDGE_API_KEY", "change_this_key")
MT5_ACCOUNT = int(os.getenv("MT5_ACCOUNT", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

app = FastAPI(title="AURUM MT5 Bridge", version="1.0")


def _auth(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


class OrderRequest(BaseModel):
    symbol: str
    action: str
    lot_size: float
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    comment: str = "AURUM"
    filling: str = "ORDER_FILLING_IOC"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/order")
def place_order(req: OrderRequest, x_api_key: str = Header(...)):
    _auth(x_api_key)

    try:
        import MetaTrader5 as mt5

        if not mt5.initialize(login=MT5_ACCOUNT, password=MT5_PASSWORD, server=MT5_SERVER):
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")

        action_map = {"BUY": mt5.ORDER_TYPE_BUY, "SELL": mt5.ORDER_TYPE_SELL}
        order_type = action_map.get(req.action.upper())
        if order_type is None:
            raise ValueError(f"Invalid action: {req.action}")

        filling_map = {
            "ORDER_FILLING_IOC": mt5.ORDER_FILLING_IOC,
            "ORDER_FILLING_FOK": mt5.ORDER_FILLING_FOK,
            "ORDER_FILLING_RETURN": mt5.ORDER_FILLING_RETURN,
        }
        filling = filling_map.get(req.filling, mt5.ORDER_FILLING_IOC)

        tick = mt5.symbol_info_tick(req.symbol)
        if tick is None:
            raise RuntimeError(f"No tick for {req.symbol}")
        price = tick.ask if req.action.upper() == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": req.lot_size,
            "type": order_type,
            "price": price,
            "sl": req.sl or 0.0,
            "tp": req.tp or 0.0,
            "comment": req.comment,
            "type_filling": filling,
            "type_time": mt5.ORDER_TIME_GTC,
        }

        result = mt5.order_send(request)
        mt5.shutdown()

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Order failed retcode={result.retcode}")

        return {
            "ticket": result.order,
            "status": "EXECUTED",
            "actual_entry": result.price,
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="MetaTrader5 package not available (Windows only)")
    except Exception as e:
        log.error("Order error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
