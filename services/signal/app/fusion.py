from .agents.base import AgentSignal

SIGNAL_WEIGHT = {"BUY": 1, "SELL": -1, "HOLD": 0}
HIGH_CONF_MACRO = 68   # macro confidence ที่สูงพอให้ macro กำหนด direction


def fuse_signals(agent_signals: list[AgentSignal], macro_signal: dict) -> dict:
    total = len(agent_signals)
    counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    raw_score = 0.0

    for ag in agent_signals:
        counts[ag.signal] += 1
        raw_score += SIGNAL_WEIGHT[ag.signal]

    macro_dir  = macro_signal.get("direction", "NEUTRAL")
    macro_conf = macro_signal.get("confidence", 50)

    # ── High-confidence macro (>=68%): macro กำหนด direction ──────────────
    # เหตุผล: qwen3.6:35b มี reasoning ดีกว่า indicator ธรรมดา
    # tech agents ทำหน้าที่ scale confidence เท่านั้น ไม่ override direction
    if macro_conf >= HIGH_CONF_MACRO and macro_dir != "NEUTRAL":
        action = "BUY" if macro_dir == "BULLISH" else "SELL"
        agree_count  = counts.get(action, 0)
        tech_agree   = agree_count / total           # 0.0–1.0

        # macro 70% weight + tech agreement 30%
        blended = int(macro_conf * 0.70 + tech_agree * 100 * 0.30)
        consensus = f"{agree_count}/{total} agents เห็นด้วยกับ macro"

        return {
            "action":              action,
            "confidence":          blended,
            "technical_consensus": consensus,
            "agent_vote_counts":   counts,
            "tech_score":          round(raw_score, 2),
        }

    # ── Normal blend: macro + tech 50/50 ──────────────────────────────────
    score = raw_score
    macro_weight = macro_conf / 100.0
    if macro_dir == "BULLISH":
        score += macro_weight * 2
    elif macro_dir == "BEARISH":
        score -= macro_weight * 2

    if score > 0.5:
        action = "BUY";  agree_count = counts["BUY"]
    elif score < -0.5:
        action = "SELL"; agree_count = counts["SELL"]
    else:
        action = "HOLD"; agree_count = counts["HOLD"]

    tech_confidence = min(100, int((abs(score) / total) * 100))
    blended         = int((tech_confidence + macro_conf) / 2)
    consensus       = f"{agree_count}/{total} agents agree"

    return {
        "action":              action,
        "confidence":          blended,
        "technical_consensus": consensus,
        "agent_vote_counts":   counts,
        "tech_score":          round(score, 2),
    }
