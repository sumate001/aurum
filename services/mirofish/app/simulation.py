import asyncio
import json
import os
import re
import uuid

import httpx

from .personas import PERSONAS
from .memory import get_memories, store_memory

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://100.94.37.18:11434")
AGENT_MODEL = os.getenv("OLLAMA_MODEL_AGENT", "qwen3:8b")
ORCHESTRATOR_MODEL = os.getenv("OLLAMA_MODEL_ORCHESTRATOR", "qwen3:14b")


def _clean(text: str) -> str:
    """Strip thinking tags, markdown fences, and tokenizer artifacts."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("▁", " ")  # SentencePiece ▁ → space
    return text.strip()


def _extract_json(text: str) -> dict:
    text = _clean(text)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}


def _extract_json_list(text: str) -> list[dict]:
    text = _clean(text)
    # try full array first
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    # fallback: extract individual objects
    results = []
    for m in re.finditer(r'\{[^{}]+\}', text, re.DOTALL):
        try:
            results.append(json.loads(m.group()))
        except Exception:
            pass
    return results


async def _call_ollama(client: httpx.AsyncClient, model: str, prompt: str, timeout: int = 300) -> str:
    resp = await client.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


async def _run_simulation_async(
    seed_document: str,
    symbol: str,
    upcoming_events: list,
    rounds: int = 3,
) -> dict:
    session_id = str(uuid.uuid4())

    persona_descriptions = "\n".join(
        f"{i+1}. **{p['name']}**: {p['personality']}"
        for i, p in enumerate(PERSONAS)
    )

    event_summary = ", ".join(e.get("event_name", "") for e in upcoming_events[:3]) or "None"

    # ─── Call 1: Multi-persona simulation (1 call, all personas together) ───
    agent_prompt = f"""You are a financial simulation engine running {rounds} rounds of analysis for {symbol}.

Simulate the following {len(PERSONAS)} market participants independently:
{persona_descriptions}

Market Intelligence:
---
{seed_document[:4000]}
---
Upcoming events: {event_summary}

For EACH persona, provide their directional view after {rounds} rounds of deliberation.
Respond as a JSON array ONLY (no text outside the array):
[
  {{"persona": "name", "direction": "BULLISH|BEARISH|NEUTRAL", "confidence": 0-100, "reasoning": "brief reason"}},
  ...
]"""

    async with httpx.AsyncClient() as client:
        try:
            raw_agents = await _call_ollama(client, AGENT_MODEL, agent_prompt, timeout=300)
            votes = _extract_json_list(raw_agents)
        except Exception as e:
            votes = []

        # ensure we have votes for all personas (fallback if parsing incomplete)
        if len(votes) < len(PERSONAS):
            for p in PERSONAS[len(votes):]:
                votes.append({"persona": p["name"], "direction": "NEUTRAL", "confidence": 50, "reasoning": "fallback"})

        # store memories per agent
        for v in votes:
            store_memory(v.get("persona", "unknown"), v.get("reasoning", ""), session_id)

        # tally scores
        direction_scores: dict[str, float] = {"BULLISH": 0.0, "BEARISH": 0.0, "NEUTRAL": 0.0}
        for v in votes:
            d = v.get("direction", "NEUTRAL")
            c = float(v.get("confidence", 50))
            direction_scores[d] = direction_scores.get(d, 0.0) + c

        dominant = max(direction_scores, key=direction_scores.get)
        avg_confidence = int(sum(v.get("confidence", 50) for v in votes) / len(votes))

        # ─── Call 2: Orchestrator synthesis ───
        orchestrator_prompt = f"""You are the AURUM Signal Orchestrator for {symbol}.

Agent simulation results ({len(votes)} participants, {rounds} rounds):
{json.dumps(votes, indent=2)}

Direction scores: {json.dumps(direction_scores)}
Dominant: {dominant} ({direction_scores[dominant]:.0f} pts)
Upcoming events: {event_summary}

Synthesize into a final trading signal. Respond as JSON ONLY:
{{"direction": "BULLISH|BEARISH|NEUTRAL", "confidence": 0-100, "recommended_tf": "M15|H1|H4|D1", "reasoning": "concise synthesis of key factors"}}"""

        try:
            raw_orch = await _call_ollama(client, ORCHESTRATOR_MODEL, orchestrator_prompt, timeout=300)
            final = _extract_json(raw_orch)
            if not final or "direction" not in final:
                final = {
                    "direction": dominant,
                    "confidence": avg_confidence,
                    "recommended_tf": "H1",
                    "reasoning": _clean(raw_orch)[:300] or "Orchestrator parse error",
                }
        except Exception as e:
            final = {
                "direction": dominant,
                "confidence": avg_confidence,
                "recommended_tf": "H1",
                "reasoning": f"Orchestrator error: {e}",
            }

    return {
        **final,
        "raw_output": {
            "votes": votes,
            "vote_scores": direction_scores,
            "total_participants": len(votes),
            "rounds": rounds,
            "session_id": session_id,
        },
    }


def run_simulation(seed_document: str, symbol: str, upcoming_events: list, rounds: int = 3) -> dict:
    return asyncio.run(_run_simulation_async(seed_document, symbol, upcoming_events, rounds))
