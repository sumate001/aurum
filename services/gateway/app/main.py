import asyncio
import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks

from .approval import save_signal, check_rate_limit, get_recent_signals
from .telegram import send_signal, build_application, TELEGRAM_BOT_TOKEN

log = logging.getLogger(__name__)

SIGNAL_MAX_PER_HOUR = int(os.getenv("SIGNAL_MAX_PER_HOUR", 3))

_tg_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tg_app
    if TELEGRAM_BOT_TOKEN:
        _tg_app = build_application()
        await _tg_app.initialize()
        await _tg_app.start()
        log.info("Telegram bot started")
    yield
    if _tg_app:
        await _tg_app.stop()
        await _tg_app.shutdown()


app = FastAPI(title="AURUM Gateway", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/signal")
async def receive_signal(signal: dict, background_tasks: BackgroundTasks):
    if signal.get("action") == "HOLD":
        log.info("Received HOLD signal, not forwarding")
        return {"status": "skipped", "reason": "HOLD"}

    if not check_rate_limit(SIGNAL_MAX_PER_HOUR):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    signal_id = save_signal(signal)
    log.info("Signal saved id=%s action=%s confidence=%d", signal_id, signal.get("action"), signal.get("confidence", 0))

    background_tasks.add_task(send_signal, signal, signal_id)
    return {"status": "pending_approval", "signal_id": signal_id}


@app.post("/simulate")
async def force_simulate():
    import httpx
    try:
        resp = httpx.post("http://aurum-collector:8000/trigger", timeout=5)
        return {"status": "triggered"}
    except Exception:
        return {"status": "triggered_async"}


@app.get("/trend-history")
def get_trend_history(limit: int = 100):
    import redis as redis_lib, json, os
    r = redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "aurum-redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )
    raw = r.lrange("aurum:trend_history", 0, limit - 1)
    return [json.loads(x) for x in raw]


@app.get("/status")
def get_trend_status():
    import redis as redis_lib, json, os
    r = redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "aurum-redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )
    raw = r.get("aurum:trend_status")
    if not raw:
        return {"direction": "UNKNOWN", "action": "HOLD", "reason": "no_data",
                "updated_at": None, "stable_since": None}
    return json.loads(raw)


@app.get("/signals")
def list_signals(limit: int = 20):
    return get_recent_signals(limit)


@app.get("/signals/{signal_id}/status")
def signal_status(signal_id: str):
    from .approval import get_signal
    sig = get_signal(signal_id)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"signal_id": signal_id, "status": sig["status"]}
