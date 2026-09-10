"""
TRACE — Scoped LLM Fallback (Milestone 3)
The ONLY place an LLM touches extraction, and it is deliberately narrow:
given one sentence plus two candidate entities, it picks exactly one of the
four fixed relation labels — or NONE. It never generates text, never writes
Cypher, never invents entities. Absent configuration → returns None and the
pipeline simply keeps its deterministic result.
"""

import json
import logging
import httpx

from app.config import settings

logger = logging.getLogger("trace.nlp")

ALLOWED_RELATIONS = ["CALLED", "TRANSFERRED_TO", "TRAVELLED_WITH", "ASSOCIATED_WITH", "NONE"]

PROMPT = """You classify relationships in one sentence for an investigative analysis tool.
Choose exactly one label for how the first entity relates to the second:
CALLED, TRANSFERRED_TO, TRAVELLED_WITH, ASSOCIATED_WITH, or NONE (if none apply).
Respond with JSON only: {{"relation": "<LABEL>", "confidence": <0.0-1.0>}}

Sentence: {sentence}
First entity: {head}
Second entity: {tail}"""


async def classify_relation(sentence: str, head: str, tail: str) -> dict | None:
    """
    Returns {"relation": str, "confidence": float} or None if unavailable/invalid.
    Hard-scoped: single-sentence classification against a fixed label set.
    """
    if not settings.llm_api_base:
        return None

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{settings.llm_api_base.rstrip('/')}/chat/completions",
                headers=(
                    {"Authorization": f"Bearer {settings.llm_api_key}"}
                    if settings.llm_api_key
                    else {}
                ),
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": PROMPT.format(sentence=sentence, head=head, tail=tail)}],
                    "temperature": 0,
                    "max_tokens": 40,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"LLM fallback unavailable: {e}")
        return None

    # Tolerate markdown fences; parse strictly from there
    try:
        if content.startswith("```"):
            content = content.strip("` \n").split("\n", 1)[-1]
        parsed = json.loads(content)
        relation = str(parsed.get("relation", "NONE")).upper()
        confidence = float(parsed.get("confidence", 0.0))
    except Exception:
        return None

    if relation not in ALLOWED_RELATIONS:
        return None
    return {"relation": relation, "confidence": max(0.0, min(1.0, confidence))}
