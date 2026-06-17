import os
import pandas as pd

from .agents.trend import TrendAgent
from .agents.momentum import MomentumAgent
from .agents.volatility import VolatilityAgent
from .agents.breakout import BreakoutAgent
from .agents.structure import StructureAgent
from .agents.smc import SMCAgent
from .agents.volume import VolumeAgent
from .fusion import fuse_signals
from .entry_quality import check_entry_quality

CONFIDENCE_THRESHOLD  = int(os.getenv("SIGNAL_CONFIDENCE_THRESHOLD", 60))
ENTRY_QUALITY_MIN     = int(os.getenv("SIGNAL_ENTRY_QUALITY_MIN", 4))   # 0-6, ต้องได้ >= 4

AGENTS = [
    TrendAgent(),
    MomentumAgent(),
    VolatilityAgent(),
    BreakoutAgent(),
    StructureAgent(),
    SMCAgent(),
    VolumeAgent(),
]


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"])


def _compute_sl_tp(action: str, entry: float, atr: float) -> dict:
    sl_mult, tp1_mult, tp2_mult = 1.5, 2.0, 3.5
    if action == "BUY":
        return {
            "sl":  round(entry - atr * sl_mult,  2),
            "tp1": round(entry + atr * tp1_mult, 2),
            "tp2": round(entry + atr * tp2_mult, 2),
        }
    elif action == "SELL":
        return {
            "sl":  round(entry + atr * sl_mult,  2),
            "tp1": round(entry - atr * tp1_mult, 2),
            "tp2": round(entry - atr * tp2_mult, 2),
        }
    return {"sl": None, "tp1": None, "tp2": None}


def analyze(symbol: str, macro_signal: dict, ohlcv: dict) -> dict:
    macro_dir  = macro_signal.get("direction", "NEUTRAL")
    macro_conf = macro_signal.get("confidence", 0)

    # ── Run technical agents on H1 (primary) ──────────────────────────────
    tf_priority = ["H1", "H4", "M15"]
    df = None
    used_tf = "H1"
    for tf in tf_priority:
        records = ohlcv.get(tf, [])
        if records and not (len(records) == 1 and "error" in records[0]):
            candidate = _records_to_df(records)
            if len(candidate) >= 20:
                df = candidate
                used_tf = tf
                break

    if df is None or len(df) < 20:
        return {
            "action": "HOLD",
            "timeframe": "H1",
            "confidence": 0,
            "technical_consensus": "insufficient data",
            "setup_type": "No Data",
            "setup_detail": "ข้อมูลราคาไม่เพียงพอ",
            "entry_quality": {"score": 0, "quality": "LOW", "details": []},
            "reasoning": "ข้อมูลราคาไม่เพียงพอสำหรับการวิเคราะห์",
            "agent_outputs": [],
        }

    # ── Agent votes ────────────────────────────────────────────────────────
    agent_signals = []
    for agent in AGENTS:
        try:
            agent_signals.append(agent.analyze(df))
        except Exception:
            pass

    fusion = fuse_signals(agent_signals, macro_signal)
    tech_action = fusion["action"]

    # ATR for SL/TP
    h  = df["high"]
    l  = df["low"]
    c  = df["close"]
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    entry = float(c.iloc[-1])

    # ── Entry quality check ────────────────────────────────────────────────
    eq = check_entry_quality(ohlcv, macro_dir)

    # ── Decide final action ────────────────────────────────────────────────
    # Conditions to fire a real BUY/SELL:
    #   1. Macro is directional (not NEUTRAL)
    #   2. Tech agents agree with macro direction
    #   3. Confidence >= threshold
    #   4. Entry quality score >= minimum (price at good entry zone)
    action = "HOLD"
    hold_reason = ""

    if macro_dir == "NEUTRAL":
        hold_reason = "Macro neutral — รอทิศทางชัดเจน"
    elif tech_action == "HOLD":
        hold_reason = f"Technical agents ไม่ชัดเจน ({fusion['technical_consensus']})"
    elif tech_action != ("BUY" if macro_dir == "BULLISH" else "SELL"):
        hold_reason = f"Technical ({tech_action}) ขัดแย้งกับ macro ({macro_dir})"
    elif fusion["confidence"] < CONFIDENCE_THRESHOLD:
        hold_reason = f"Confidence {fusion['confidence']}% ต่ำกว่า {CONFIDENCE_THRESHOLD}%"
    elif eq["score"] < ENTRY_QUALITY_MIN:
        hold_reason = f"Entry quality {eq['score']}/6 ต่ำ — {eq['setup_type']}"
    else:
        action = tech_action  # BUY or SELL

    levels = _compute_sl_tp(action, entry, atr) if action != "HOLD" else {"sl": None, "tp1": None, "tp2": None}

    # ── Reasoning text ─────────────────────────────────────────────────────
    if action != "HOLD":
        reasoning = (
            f"Setup: {eq['setup_type']} | "
            f"Macro: {macro_dir} {macro_conf}% | "
            f"Technical: {fusion['technical_consensus']} | "
            f"Quality: {eq['quality']} ({eq['score']}/6) | "
            + " | ".join(eq["details"])
        )
    else:
        reasoning = (
            f"HOLD: {hold_reason} | "
            f"Macro: {macro_dir} {macro_conf}% | "
            f"Setup: {eq['setup_type']} | "
            + " | ".join(eq["details"])
        )

    return {
        "symbol": symbol,
        "action": action,
        "timeframe": used_tf,
        "entry": round(entry, 2),
        "sl": levels["sl"],
        "tp1": levels["tp1"],
        "tp2": levels["tp2"],
        "confidence": fusion["confidence"] if action != "HOLD" else 0,
        "macro_bias": macro_dir,
        "macro_confidence": macro_conf,
        "technical_consensus": fusion["technical_consensus"],
        "setup_type": eq["setup_type"],
        "setup_detail": " | ".join(eq["details"]),
        "entry_quality": eq,
        "reasoning": reasoning,
        "agent_outputs": [
            {"agent_name": s.agent_name, "signal": s.signal, "value": s.value, "metadata": s.metadata}
            for s in agent_signals
        ],
        "raw_macro": macro_signal,
        "raw_technical": fusion,
    }
