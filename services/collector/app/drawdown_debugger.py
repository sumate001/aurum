"""
Drawdown Debugger — triggers when loss streak >= DRAWDOWN_STREAK_TRIGGER.

Queries the executions table, identifies the loss pattern,
and generates an LLM diagnostic to help course-correct the signal strategy.
"""

import json
import logging
import os
import re

import httpx

OLLAMA_URL            = os.getenv("OLLAMA_BASE_URL", "http://100.94.37.18:11434")
ADHD_MODEL            = os.getenv("ADHD_MODEL", os.getenv("OLLAMA_MODEL_ORCHESTRATOR", "qwen3:14b"))
LOSS_STREAK_TRIGGER   = int(os.getenv("DRAWDOWN_STREAK_TRIGGER", 3))

log = logging.getLogger(__name__)

_PROMPT = """\
You are the AURUM Drawdown Debugger. Analyze {streak} consecutive losing trades \
and identify what the signal system got wrong.

Recent executions (most recent first):
{executions_json}

Diagnose the failure pattern systematically:
1. Was macro bias (BULLISH/BEARISH) systematically wrong?
2. Were entry quality scores misleading (high score but bad outcome)?
3. Market regime mismatch — trending signal in choppy market or vice versa?
4. Setup type failure — is a specific setup type consistently failing?
5. Timing — same session, same market condition?

Respond as JSON ONLY:
{{
  "root_cause": "one-sentence primary diagnosis",
  "failure_pattern": "what all losing trades share in common",
  "market_regime": "trending|ranging|choppy|news-driven|unknown",
  "failing_setup": "setup type name or null",
  "recommendations": [
    "specific action 1",
    "specific action 2",
    "specific action 3"
  ],
  "severity": "low|medium|high",
  "suggested_pause_hours": <integer 0-24>
}}"""


def get_loss_streak(conn) -> tuple[int, list[dict]]:
    """Return (streak_count, recent_closed_executions)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.id, e.signal_id, e.status, e.pnl, e.executed_at,
                   s.action, s.confidence, s.macro_bias,
                   s.technical_consensus, s.reasoning
            FROM executions e
            JOIN signals s ON e.signal_id = s.id
            WHERE e.status IN ('CLOSED_TP', 'CLOSED_SL', 'CLOSED_MANUAL')
            ORDER BY e.executed_at DESC
            LIMIT 10
        """)
        rows = cur.fetchall()

    if not rows:
        return 0, []

    executions = [
        {
            "id":                  str(row[0]),
            "signal_id":           str(row[1]),
            "status":              row[2],
            "pnl":                 float(row[3]) if row[3] is not None else 0.0,
            "executed_at":         str(row[4]),
            "action":              row[5],
            "confidence":          row[6],
            "macro_bias":          row[7],
            "technical_consensus": row[8],
            "reasoning":           (row[9] or "")[:200],
        }
        for row in rows
    ]

    streak = 0
    for ex in executions:
        if ex["pnl"] < 0 or ex["status"] == "CLOSED_SL":
            streak += 1
        else:
            break

    return streak, executions


def _extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start, end = text.find("{"), text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}


def analyze_drawdown(conn) -> dict | None:
    """
    Check for loss streak and run ADHD diagnostic if threshold is met.
    Returns the analysis dict, or None if streak < trigger.
    """
    streak, executions = get_loss_streak(conn)
    if streak < LOSS_STREAK_TRIGGER:
        return None

    log.warning(
        "Loss streak: %d consecutive losses — ADHD drawdown debugger triggered (model=%s)",
        streak, ADHD_MODEL,
    )

    prompt = _PROMPT.format(
        streak=streak,
        executions_json=json.dumps(executions[:streak], indent=2, default=str),
    )
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": ADHD_MODEL, "prompt": prompt, "stream": False},
            timeout=300,
        )
        resp.raise_for_status()
        result = _extract_json(resp.json().get("response", ""))
        result["streak"] = streak
        result["triggered_by"] = [ex["id"] for ex in executions[:streak]]
        log.warning(
            "Drawdown analysis: streak=%d cause=%r severity=%s pause_h=%s",
            streak,
            result.get("root_cause"),
            result.get("severity"),
            result.get("suggested_pause_hours", 0),
        )
        return result
    except Exception as e:
        log.error("Drawdown analysis failed: %s", e)
        return {"streak": streak, "error": str(e)}
