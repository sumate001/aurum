import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta

import httpx
import psycopg2
import redis as redis_lib
from apscheduler.schedulers.blocking import BlockingScheduler

from .seed_builder import build_seed_document
from .sources.calendar import fetch_calendar_events
from .sources.price import fetch_ohlcv
from .drawdown_debugger import analyze_drawdown

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SYMBOL               = os.getenv("MT5_SYMBOL", "GOLD#")
MIROFISH_URL         = os.getenv("MIROFISH_URL", "http://aurum-mirofish:8000")
SIGNAL_URL           = os.getenv("SIGNAL_URL", "http://aurum-signal:8000")
GATEWAY_URL          = os.getenv("GATEWAY_URL", "http://aurum-gateway:8000")
SIMULATION_ROUNDS    = int(os.getenv("MIROFISH_SIMULATION_ROUNDS", 30))
CONFIDENCE_THRESHOLD      = int(os.getenv("SIGNAL_CONFIDENCE_THRESHOLD", 60))
RECONFIRM_HOURS           = int(os.getenv("SIGNAL_RECONFIRM_HOURS", 4))
CONF_SURGE_THRESHOLD      = int(os.getenv("SIGNAL_CONF_SURGE", 15))
MAX_DAILY_SIGNALS         = int(os.getenv("SIGNAL_MAX_DAILY", 3))
OFF_SESSION_CONF_OVERRIDE = int(os.getenv("SIGNAL_OFF_SESSION_CONFIDENCE", 78))

# Trading sessions in UTC (hour_start inclusive, hour_end exclusive)
# Asian:  01:00–07:00 UTC  =  08:00–14:00 Bangkok
# London: 07:00–12:00 UTC  =  14:00–19:00 Bangkok
# NY:     13:00–18:00 UTC  =  20:00–01:00 Bangkok
SESSIONS_UTC = {
    "asian":  (1, 7),
    "london": (7, 12),
    "ny":     (13, 18),
}

_paused = False


# ── DB / Redis helpers ─────────────────────────────────────────────────────

def _get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "aurum-postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "aurum"),
        user=os.getenv("POSTGRES_USER", "aurum"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def _get_redis() -> redis_lib.Redis:
    return redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "aurum-redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )


def _save_seed(conn, symbol: str, content: str, sources: dict) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO seed_documents (symbol, content, sources, word_count) VALUES (%s, %s, %s, %s) RETURNING id",
            (symbol, content, json.dumps(sources), len(content.split())),
        )
        seed_id = cur.fetchone()[0]
    conn.commit()
    return str(seed_id)


def _save_simulation(conn, seed_id: str, result: dict) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO simulation_reports
               (seed_id, direction, confidence, recommended_tf, reasoning, raw_output)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                seed_id,
                result.get("direction"),
                result.get("confidence"),
                result.get("recommended_tf"),
                result.get("reasoning"),
                json.dumps(result.get("raw_output", {})),
            ),
        )
        sim_id = cur.fetchone()[0]
    conn.commit()
    return str(sim_id)


# ── Session helpers ────────────────────────────────────────────────────────

def _current_session(now_utc: datetime) -> str | None:
    """Return 'london' | 'ny' | None (off-hours)"""
    h = now_utc.hour
    for name, (start, end) in SESSIONS_UTC.items():
        if start <= h < end:
            return name
    return None


def _daily_signal_count(r: redis_lib.Redis, date_str: str) -> int:
    val = r.get(f"aurum:daily_signals:{date_str}")
    return int(val) if val else 0


def _increment_daily_count(r: redis_lib.Redis, date_str: str):
    key = f"aurum:daily_signals:{date_str}"
    r.incr(key)
    r.expire(key, 90000)  # 25 hours TTL


# ── Trend status (Redis) ───────────────────────────────────────────────────

def _get_last_signal(r: redis_lib.Redis) -> dict | None:
    raw = r.get("aurum:last_signal")
    return json.loads(raw) if raw else None


def _set_last_signal(r: redis_lib.Redis, signal: dict):
    r.setex("aurum:last_signal", 86400 * 7, json.dumps(signal, default=str))


def _save_trend_status(r: redis_lib.Redis, macro: dict, signal: dict,
                       reason: str, stable_since: str, session: str | None,
                       daily_count: int):
    status = {
        "direction":           macro.get("direction", "NEUTRAL"),
        "macro_confidence":    macro.get("confidence", 0),
        "action":              signal.get("action", "HOLD"),
        "signal_confidence":   signal.get("confidence", 0),
        "technical_consensus": signal.get("technical_consensus", ""),
        "setup_type":          signal.get("setup_type", ""),
        "setup_detail":        signal.get("setup_detail", ""),
        "entry_quality":       signal.get("entry_quality", {}),
        "reasoning":           signal.get("reasoning", ""),
        "updated_at":          datetime.now(timezone.utc).isoformat(),
        "stable_since":        stable_since,
        "reason":              reason,
        "session":             session,
        "daily_signals_sent":  daily_count,
        "max_daily_signals":   MAX_DAILY_SIGNALS,
        "entry":               signal.get("entry"),
        "sl":                  signal.get("sl"),
        "tp1":                 signal.get("tp1"),
        "tp2":                 signal.get("tp2"),
    }
    r.setex("aurum:trend_status", 7200, json.dumps(status, default=str))
    log.info("Trend status: dir=%s action=%s setup=%s quality=%s reason=%s session=%s",
             status["direction"], status["action"],
             status.get("setup_type"), status.get("entry_quality", {}).get("quality"),
             reason, session)


# ── Signal deduplication logic ─────────────────────────────────────────────

def _should_send_signal(new_sig: dict, last_sig: dict | None,
                        session: str | None, daily_count: int) -> tuple[bool, str]:
    """Return (should_send, reason)"""

    # Gate 1: session filter (high-confidence signals can bypass off-hours)
    if session is None:
        if new_sig.get("confidence", 0) < OFF_SESSION_CONF_OVERRIDE:
            return False, "off_session"

    # Gate 2: daily limit
    if daily_count >= MAX_DAILY_SIGNALS:
        return False, "daily_limit_reached"

    # Gate 3: HOLD never goes to gateway
    if new_sig.get("action") == "HOLD":
        return False, "hold"

    if last_sig is None:
        return True, "first_signal"

    new_action  = new_sig.get("action")
    last_action = last_sig.get("action")

    # Direction flipped → always alert
    if new_action != last_action:
        return True, "direction_changed"

    # Confidence surged significantly
    conf_diff = new_sig.get("confidence", 0) - last_sig.get("confidence", 0)
    if conf_diff >= CONF_SURGE_THRESHOLD:
        return True, "confidence_surge"

    # Materially different entry (pullback created new opportunity)
    try:
        last_entry = float(last_sig.get("entry") or 0)
        new_entry  = float(new_sig.get("entry") or 0)
        new_sl     = float(new_sig.get("sl") or 0)
        if new_entry and new_sl:
            atr_approx = abs(new_entry - new_sl) / 1.5
            if atr_approx > 0 and abs(new_entry - last_entry) > 1.5 * atr_approx:
                return True, "new_entry_point"
    except (TypeError, ValueError):
        pass

    # Periodic reconfirmation (max once per session)
    try:
        last_ts = datetime.fromisoformat(
            str(last_sig.get("created_at", "")).replace("Z", "+00:00")
        )
        if datetime.now(timezone.utc) - last_ts > timedelta(hours=RECONFIRM_HOURS):
            return True, "periodic_reconfirmation"
    except Exception:
        pass

    return False, "direction_confirmed"


# ── Main cycle ─────────────────────────────────────────────────────────────

def run_cycle():
    if _paused:
        log.info("Collector paused, skipping cycle")
        return

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    session = _current_session(now_utc)
    date_str = now_utc.strftime("%Y-%m-%d")

    log.info("Cycle start symbol=%s session=%s utc=%s", SYMBOL, session or "off-hours", now_utc.strftime("%H:%M"))

    conn = None
    r = _get_redis()
    daily_count = _daily_signal_count(r, date_str)

    try:
        conn = _get_db()

        calendar_events = fetch_calendar_events()
        ohlcv = fetch_ohlcv(SYMBOL)

        seed_content, sources = build_seed_document(SYMBOL, ohlcv, calendar_events)
        seed_id = _save_seed(conn, SYMBOL, seed_content, sources)
        log.info("Seed saved id=%s words=%d", seed_id, len(seed_content.split()))

        upcoming = [e for e in calendar_events if "error" not in e]

        # ── MiroFish simulation ────────────────────────────────────────────
        sim_resp = httpx.post(
            f"{MIROFISH_URL}/simulate",
            json={
                "seed_document":     seed_content,
                "symbol":            SYMBOL,
                "upcoming_events":   upcoming,
                "simulation_rounds": SIMULATION_ROUNDS,
            },
            timeout=600,
        )
        sim_resp.raise_for_status()
        macro_signal = sim_resp.json()
        _save_simulation(conn, seed_id, macro_signal)
        log.info("Simulation done direction=%s confidence=%d",
                 macro_signal.get("direction"), macro_signal.get("confidence"))

        if macro_signal.get("confidence", 0) < CONFIDENCE_THRESHOLD:
            log.info("Macro confidence too low (%d)", macro_signal.get("confidence", 0))
            last = _get_last_signal(r)
            stable_since = last.get("stable_since", now_iso) if last else now_iso
            _save_trend_status(r, macro_signal,
                               {"action": "HOLD", "confidence": 0, "setup_type": "Macro ไม่ชัดเจน"},
                               "low_confidence", stable_since, session, daily_count)
            _log_history(r, now_iso, macro_signal, {"action": "HOLD", "confidence": 0}, False, "low_confidence")
            return

        # ── Technical + entry quality analysis ────────────────────────────
        sig_resp = httpx.post(
            f"{SIGNAL_URL}/analyze",
            json={"symbol": SYMBOL, "macro_signal": macro_signal, "ohlcv": ohlcv},
            timeout=60,
        )
        sig_resp.raise_for_status()
        signal = sig_resp.json()
        log.info("Signal: action=%s setup=%s quality=%s",
                 signal.get("action"),
                 signal.get("setup_type"),
                 signal.get("entry_quality", {}).get("quality"))

        # ── Decide whether to push to gateway ─────────────────────────────
        last_signal = _get_last_signal(r)
        should_send, reason = _should_send_signal(signal, last_signal, session, daily_count)

        if reason in ("first_signal", "direction_changed"):
            stable_since = now_iso
        else:
            stable_since = (last_signal or {}).get("stable_since", now_iso)

        _save_trend_status(r, macro_signal, signal, reason, stable_since, session, daily_count)
        _log_history(r, now_iso, macro_signal, signal, should_send and signal.get("action") != "HOLD", reason)

        if should_send:
            gw_resp = httpx.post(f"{GATEWAY_URL}/signal", json=signal, timeout=30)
            gw_resp.raise_for_status()
            signal["created_at"] = now_iso
            signal["stable_since"] = stable_since
            _set_last_signal(r, signal)
            _increment_daily_count(r, date_str)
            log.info("Signal sent reason=%s action=%s confidence=%d daily=%d/%d",
                     reason, signal.get("action"), signal.get("confidence"),
                     daily_count + 1, MAX_DAILY_SIGNALS)
        else:
            log.info("No signal sent reason=%s action=%s session=%s daily=%d/%d",
                     reason, signal.get("action"), session or "off", daily_count, MAX_DAILY_SIGNALS)

        # ── ADHD Drawdown check ────────────────────────────────────────────
        _check_drawdown(conn, r)

    except Exception as e:
        log.error("Cycle failed: %s", e, exc_info=True)
    finally:
        if conn:
            conn.close()


def _check_drawdown(conn, r: redis_lib.Redis):
    """Run ADHD drawdown analysis and cache result in Redis if streak triggered."""
    try:
        result = analyze_drawdown(conn)
        if result is None:
            return
        r.setex("aurum:drawdown_alert", 86400, json.dumps(result, default=str))
        pause_h = result.get("suggested_pause_hours", 0)
        if pause_h and pause_h > 0:
            log.warning(
                "Drawdown debugger suggests pausing %dh — "
                "root_cause=%r severity=%s (manual review required)",
                pause_h, result.get("root_cause"), result.get("severity"),
            )
        try:
            httpx.post(
                f"{GATEWAY_URL}/drawdown-alert",
                json=result,
                timeout=10,
            )
        except Exception:
            pass  # gateway endpoint is optional; log already captured the alert
    except Exception as e:
        log.warning("Drawdown check error (non-fatal): %s", e)


def _log_history(r: redis_lib.Redis, now_iso: str, macro: dict, signal: dict,
                 sent: bool, reason: str):
    entry = {
        "checked_at":  now_iso,
        "direction":   macro.get("direction"),
        "action":      signal.get("action"),
        "confidence":  signal.get("confidence"),
        "setup_type":  signal.get("setup_type", ""),
        "quality":     signal.get("entry_quality", {}).get("quality", ""),
        "sent_signal": sent,
        "reason":      reason,
    }
    r.lpush("aurum:trend_history", json.dumps(entry, default=str))
    r.ltrim("aurum:trend_history", 0, 199)


# ── Scheduler ─────────────────────────────────────────────────────────────

def main():
    log.info("Aurum Collector starting up")
    time.sleep(10)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_cycle, "cron", minute="*/15", id="cycle_15m")

    log.info("Scheduler started — session-aware, max %d signals/day", MAX_DAILY_SIGNALS)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Collector stopped")


if __name__ == "__main__":
    main()
