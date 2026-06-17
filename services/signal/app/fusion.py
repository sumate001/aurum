import pandas as pd
from .agents.base import AgentSignal


SIGNAL_WEIGHT = {"BUY": 1, "SELL": -1, "HOLD": 0}


def fuse_signals(agent_signals: list[AgentSignal], macro_signal: dict) -> dict:
    total = len(agent_signals)
    counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    score = 0.0

    for ag in agent_signals:
        counts[ag.signal] += 1
        score += SIGNAL_WEIGHT[ag.signal]

    macro_dir = macro_signal.get("direction", "NEUTRAL")
    macro_conf = macro_signal.get("confidence", 50)
    macro_weight = macro_conf / 100.0

    if macro_dir == "BULLISH":
        score += macro_weight * 2
    elif macro_dir == "BEARISH":
        score -= macro_weight * 2

    if score > 0.5:
        action = "BUY"
        agree_count = counts["BUY"]
    elif score < -0.5:
        action = "SELL"
        agree_count = counts["SELL"]
    else:
        action = "HOLD"
        agree_count = counts["HOLD"]

    tech_confidence = int((abs(score) / (total + 2)) * 100)
    blended_confidence = int((tech_confidence + macro_conf) / 2)

    consensus = f"{agree_count}/{total} agents agree"
    return {
        "action": action,
        "confidence": blended_confidence,
        "technical_consensus": consensus,
        "agent_vote_counts": counts,
        "tech_score": round(score, 2),
    }
