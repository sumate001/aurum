import os
import httpx

MT5_BRIDGE_URL = os.getenv("MT5_BRIDGE_URL", "")
MT5_BRIDGE_API_KEY = os.getenv("MT5_BRIDGE_API_KEY", "")
MT5_SYMBOL = os.getenv("MT5_SYMBOL", "GOLD#")
MT5_FILLING = os.getenv("MT5_FILLING", "ORDER_FILLING_IOC")


def execute_order(signal: dict, lot_size: float = 0.1) -> dict:
    if not MT5_BRIDGE_URL:
        raise RuntimeError("MT5_BRIDGE_URL not configured")

    payload = {
        "symbol": signal.get("symbol", MT5_SYMBOL),
        "action": signal["action"],
        "lot_size": lot_size,
        "entry": signal.get("entry"),
        "sl": signal.get("sl"),
        "tp": signal.get("tp1"),
        "comment": f"AURUM",
        "filling": MT5_FILLING,
    }
    resp = httpx.post(
        f"{MT5_BRIDGE_URL}/order",
        headers={"X-API-Key": MT5_BRIDGE_API_KEY},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
