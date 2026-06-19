"""
ADHD Hypothesis Generator — divergent pre-simulation analysis.

Generates contrarian market hypotheses before MiroFish agent voting
so the simulation is forced to consider non-consensus scenarios.
ADHD mode: lateral thinking, challenge assumptions, surface hidden risks.
"""

import json
import logging
import os
import re

import httpx

OLLAMA_URL  = os.getenv("OLLAMA_BASE_URL", "http://100.94.37.18:11434")
ADHD_MODEL  = os.getenv("ADHD_MODEL", os.getenv("OLLAMA_MODEL_ORCHESTRATOR", "qwen3:14b"))

log = logging.getLogger(__name__)

_PROMPT = """\
You are an ADHD-mode contrarian analyst for {symbol}.
Your job: generate divergent hypotheses that mainstream analysis overlooks.
Think laterally — challenge the dominant narrative, surface tail risks, \
consider second-order effects, false signals, and hidden market forces.

Market Context:
---
{seed_document}
---

Generate exactly 4 alternative scenarios. Each must challenge or stress-test \
the most obvious interpretation of the above context.

Respond as a JSON array ONLY (no text outside):
[
  {{
    "hypothesis": "concise contrarian scenario (1-2 sentences)",
    "direction": "BULLISH|BEARISH|NEUTRAL",
    "probability": <integer 5-35>,
    "key_trigger": "what event/data would confirm this scenario"
  }},
  ...
]"""


def _parse(text: str) -> list[dict]:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start, end = text.find("["), text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            items = json.loads(text[start:end])
            return [h for h in items if isinstance(h, dict) and "hypothesis" in h][:5]
        except json.JSONDecodeError:
            pass
    # fallback: extract individual objects
    results = []
    for m in re.finditer(r'\{[^{}]+\}', text, re.DOTALL):
        try:
            obj = json.loads(m.group())
            if "hypothesis" in obj:
                results.append(obj)
        except Exception:
            pass
    return results[:5]


async def generate_hypotheses(
    client: httpx.AsyncClient,
    seed_document: str,
    symbol: str,
) -> list[dict]:
    prompt = _PROMPT.format(symbol=symbol, seed_document=seed_document[:3000])
    try:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": ADHD_MODEL, "prompt": prompt, "stream": False},
            timeout=300,
        )
        resp.raise_for_status()
        hypotheses = _parse(resp.json().get("response", ""))
        log.info("ADHD hypotheses generated: %d scenarios (model=%s)", len(hypotheses), ADHD_MODEL)
        return hypotheses
    except Exception as e:
        log.warning("Hypothesis generation failed (skipping): %s", e)
        return []


def format_for_simulation(hypotheses: list[dict]) -> str:
    """Format hypothesis list into a markdown block for injection into agent prompts."""
    if not hypotheses:
        return ""
    lines = [
        "## ⚡ ADHD Pre-Analysis: Divergent Hypotheses",
        "These alternative scenarios were generated BEFORE the consensus vote.",
        "Each participant should independently consider whether any of these applies.\n",
    ]
    for i, h in enumerate(hypotheses, 1):
        direction = h.get("direction", "NEUTRAL")
        prob      = h.get("probability", "?")
        hyp       = h.get("hypothesis", "")
        trigger   = h.get("key_trigger", "")
        lines.append(f"{i}. [{direction} ~{prob}%] {hyp}")
        if trigger:
            lines.append(f"   Trigger: {trigger}")
    lines.append("")
    return "\n".join(lines)
