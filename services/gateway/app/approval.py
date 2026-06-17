import json
import os
import psycopg2
import redis


def _get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "aurum-postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "aurum"),
        user=os.getenv("POSTGRES_USER", "aurum"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def _get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "aurum-redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )


def save_signal(signal: dict) -> str:
    conn = _get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO signals
                   (symbol, broker, action, timeframe, entry, sl, tp1, tp2, confidence,
                    macro_bias, macro_confidence, technical_consensus, reasoning,
                    upcoming_events, status, raw_macro, raw_technical)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    signal.get("symbol", "GOLD#"),
                    "XM",
                    signal.get("action"),
                    signal.get("timeframe"),
                    signal.get("entry"),
                    signal.get("sl"),
                    signal.get("tp1"),
                    signal.get("tp2"),
                    signal.get("confidence"),
                    signal.get("macro_bias"),
                    signal.get("macro_confidence"),
                    signal.get("technical_consensus"),
                    signal.get("reasoning"),
                    json.dumps(signal.get("upcoming_events", [])),
                    "PENDING_APPROVAL",
                    json.dumps(signal.get("raw_macro", {})),
                    json.dumps(signal.get("raw_technical", {})),
                ),
            )
            sig_id = str(cur.fetchone()[0])
        conn.commit()
        return sig_id
    finally:
        conn.close()


def update_signal_status(signal_id: str, status: str) -> None:
    conn = _get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE signals SET status=%s WHERE id=%s", (status, signal_id))
        conn.commit()
    finally:
        conn.close()


def get_signal(signal_id: str) -> dict | None:
    conn = _get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM signals WHERE id=%s", (signal_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
    finally:
        conn.close()


def get_recent_signals(limit: int = 10) -> list[dict]:
    conn = _get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM signals ORDER BY created_at DESC LIMIT %s", (limit,)
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def check_rate_limit(max_per_hour: int = 3) -> bool:
    r = _get_redis()
    key = "aurum:signal_count"
    count = r.get(key)
    if count and int(count) >= max_per_hour:
        return False
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 3600)
    pipe.execute()
    return True
