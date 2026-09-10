"""
TRACE — Scoped NL Chat (Milestone 11)
The ONLY chat feature, and it is deliberately narrow:
  1. Extract exactly two target entities from the investigator's question
     (deterministic: match against graph node names/aliases — the LLM never
     parses the question and never sees the graph schema).
  2. Deterministic Neo4j shortest-path query (fixed Cypher, parameterized).
  3. LLM summarizes the retrieved path into prose — grounded strictly in the
     retrieved path + snippets. No LLM-generated Cypher. No freeform RAG.
  4. Stream over SSE. Without an LLM configured, a deterministic summary is
     streamed instead — the feature degrades, never breaks.
"""

import json
import re

from rapidfuzz import fuzz
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.auth.dependencies import get_current_user
from app.db.neo4j_driver import run_cypher
from app.db.postgres import get_pool
from app.config import settings

router = APIRouter(prefix="/api/cases", tags=["chat"])

MAX_HOPS = 4
FUZZY_THRESHOLD = 90  # min score for a fuzzy alias match — below this we fail closed
STOPWORDS = {
    "how", "is", "are", "the", "a", "an", "to", "connected", "related", "linked",
    "and", "of", "in", "on", "with", "what", "who", "whom", "which", "tell", "me",
    "about", "show", "between", "from", "does", "do", "know", "any", "connection",
    "path", "relationship", "relate", "relates", "there", "anyone",
}


def _extract_candidates(question: str) -> list[str]:
    """
    Deterministic candidate spans: quoted strings, capitalized bigrams/unigrams,
    phone/plate-like tokens, plus plain word tokens — stopwords and filler
    removed. Bare lowercase tokens are included on purpose: matching is fuzzy
    and case-insensitive, so a question like "how does khan connect to rohan"
    still resolves to the graph entities. Resolution itself stays deterministic
    (match against known names/aliases only — never guessed).
    """
    q = question.strip()
    candidates = []

    # Quoted names first
    candidates.extend(re.findall(r'"([^"]+)"', q))

    # Strip punctuation, tokenize
    cleaned = re.sub(r"[^A-Za-z0-9\s\-\+\.]", " ", q)
    tokens = [t for t in cleaned.split() if t and t.lower() not in STOPWORDS]

    # Capitalized bigrams (e.g. "Rohan Mehra"), then unigrams
    for i in range(len(tokens) - 1):
        if tokens[i][0].isupper() and tokens[i + 1][0].isupper():
            candidates.append(f"{tokens[i]} {tokens[i+1]}")
    candidates.extend(t for t in tokens if t and t[0].isupper())
    candidates.extend(t for t in tokens if any(c.isdigit() for c in t) and len(t) >= 6)
    # Bare word tokens (lowercase included) so natural phrasing can still match
    candidates.extend(t for t in tokens if len(t) >= 4)

    return candidates


def _score_candidate(cand: str, name: str) -> float:
    """
    Score a candidate span against one known name/alias (0–100).
    Deterministic: exact → separator-insensitive containment for identifiers →
    RapidFuzz token-set ratio for loose word matches.
    """
    cl, nl = cand.lower().strip(), name.lower().strip()
    if not cl or not nl:
        return 0.0
    if cl == nl:
        return 100.0
    # Identifier-style candidates (phones, plates, accounts): compare with all
    # separators stripped so "9876543210" matches "+91-98765-43210".
    if any(ch.isdigit() for ch in cl):
        c_norm = re.sub(r"[^a-z0-9]", "", cl)
        n_norm = re.sub(r"[^a-z0-9]", "", nl)
        if len(c_norm) >= 4 and c_norm in n_norm:
            return 98.0
        return float(fuzz.token_set_ratio(cl, nl))
    # Word containment: "khan" → "Fatima Khan" (guard against tiny tokens)
    if len(cl) >= 4 and cl in nl:
        return 97.0
    return float(fuzz.token_set_ratio(cl, nl))


def _match_nodes(candidates: list[str], nodes: list[dict]) -> tuple[list[dict], list[str | None]]:
    """
    Match candidate spans against node names + aliases (case-insensitive, fuzzy
    via RapidFuzz, with a hard threshold). FAILS CLOSED: a candidate that does
    not clearly match a known name/alias is dropped — the matcher never guesses.
    Returns (unique_nodes_in_match_order, node_id_per_candidate).
    Multiple candidates MAY map to the same node — that's how the caller
    detects "both names are the same entity after merge decisions".
    """
    matched: list[dict] = []
    per_candidate: list[str | None] = []
    for cand in candidates:
        best_node: dict | None = None
        best_score = 0.0
        for n in nodes:
            names = [n["label"]] + list(n.get("aliases") or [])
            for name in names:
                if not name:
                    continue
                score = _score_candidate(cand, name)
                if score > best_score:
                    best_node, best_score = n, score
        if best_node is not None and best_score >= FUZZY_THRESHOLD:
            if not matched or matched[-1]["id"] != best_node["id"]:
                matched.append(best_node)
            per_candidate.append(best_node["id"])
        else:
            per_candidate.append(None)
    return matched, per_candidate


def _fixed_path_cypher() -> str:
    """The ONLY Cypher the chat feature ever runs (fixed text, parameters only)."""
    return f"""
    MATCH (a:Entity), (b:Entity)
    WHERE a.entity_id = $a_id AND b.entity_id = $b_id
    MATCH p = shortestPath((a)-[:LINKED*1..{MAX_HOPS}]-(b))
    RETURN [x IN nodes(p) | x.entity_id] AS node_ids,
           [x IN nodes(p) | x.name] AS node_names,
           [x IN nodes(p) | x.entity_type] AS node_types,
           [r IN relationships(p) | r.relation] AS rels,
           length(p) AS hops
    """


async def _fetch_provenance(prov_ids: list[str]) -> list[dict]:
    """Verbatim snippets for provenance ids (path nodes/edges)."""
    if not prov_ids:
        return []
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT e.id, e.snippet, e.page, e.paragraph, d.filename
           FROM extraction_log e JOIN documents d ON d.id = e.document_id
           WHERE e.id = ANY($1::uuid[]) LIMIT 8""",
        prov_ids,
    )
    return [
        {
            "provenance_id": str(r["id"]),
            "filename": r["filename"],
            "page": r["page"],
            "paragraph": r["paragraph"],
            "snippet": r["snippet"],
        }
        for r in rows
    ]


def _deterministic_summary(matched: list[dict], path: dict, citations: list[dict]) -> str:
    """Grounded, template-based summary used when no LLM is configured."""
    a, b = matched[0], matched[1]
    if not path:
        return (
            f"No connection of up to {MAX_HOPS} steps was found between "
            f"{a['label']} and {b['label']} in this case graph, based on currently "
            "extracted and confirmed links."
        )
    chain = []
    for i, name in enumerate(path["node_names"]):
        chain.append(name)
        if i < len(path["rels"]):
            chain.append(f"-[{path['rels'][i].replace('_', ' ').lower()}]->")
    hops = path["hops"]
    src_note = f" Sources: {len(citations)} verbatim snippet(s) cited below." if citations else ""
    return (
        f"{a['label']} and {b['label']} are connected through {hops} step(s): "
        + " ".join(chain)
        + f". This path reflects {hops} confirmed link(s) extracted from case documents."
        + src_note
    )


async def _llm_summary_stream(question: str, matched: list[dict], path: dict | None, citations: list[dict]):
    """
    Stream a strictly-grounded summary from the configured LLM.
    The prompt contains ONLY the retrieved path facts and snippets — never the
    graph schema, never freeform instructions. Yields text chunks.
    """
    import httpx

    a, b = matched[0], matched[1]
    if path:
        chain = []
        for i, name in enumerate(path["node_names"]):
            chain.append(name)
            if i < len(path["rels"]):
                chain.append(f"-[{path['rels'][i].replace('_', ' ').lower()}]->")
        path_text = " ".join(chain)
    else:
        path_text = f"No path of up to {MAX_HOPS} steps exists between the two entities."

    snippets = "\n".join(
        f"- ({c['filename']} p.{c['page']} para.{c['paragraph']}) \"{c['snippet']}\""
        for c in citations
    ) or "(no snippets retrieved)"

    prompt = f"""You summarize investigation-graph results for an analyst.
Using ONLY the facts below, answer the question in 3-5 plain sentences.
Do not invent entities, links, or details. If the path is empty, say so.

Question: {question}
Entity A: {a['label']}
Entity B: {b['label']}
Retrieved path: {path_text}
Source snippets:
{snippets}"""

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{settings.llm_api_base.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {},
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 300,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue


@router.get("/{case_id}/chat")
async def chat(case_id: str, q: str, current_user: dict = Depends(get_current_user)):
    """SSE stream: 'meta' → 'tokens'* → 'citations' → 'done'."""

    async def event_stream():
        # ── 1) Deterministic entity matching ──────────────────────────
        node_recs = await run_cypher(
            "MATCH (n:Entity) WHERE $case IN n.case_ids "
            "RETURN n.entity_id AS id, n.name AS label, n.aliases AS aliases, n.provenance_ids AS prov",
            {"case": case_id},
        )
        nodes = [dict(r) for r in node_recs]
        nodes_map = {n["id"]: n for n in nodes}
        candidates = _extract_candidates(q)
        matched, per_candidate = _match_nodes(candidates, nodes)

        yield f"data: {json.dumps({'type': 'meta', 'matched': [{'id': m['id'], 'label': m['label']} for m in matched]})}\n\n"

        if len(matched) < 2:
            # Distinguish "no entities found" from "both names are one entity"
            first = per_candidate[0] if per_candidate else None
            same_entity = bool(first) and sum(1 for x in per_candidate if x == first) >= 2
            if same_entity:
                label = matched[0]["label"]
                msg = (
                    f"Both names in the question refer to the same entity ({label}) after "
                    "accepted merge decisions, so there is no separate connection path to trace."
                )
            else:
                msg = (
                    "Could not identify two entities in the question. Name them explicitly, "
                    "e.g. How is Rohan Mehra connected to Anita Desai?"
                )
            yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return

        a, b = matched[0], matched[1]

        # ── 2) Fixed, deterministic path query ────────────────────────
        path = None
        path_recs = await run_cypher(
            _fixed_path_cypher(), {"a_id": a["id"], "b_id": b["id"]},
        )
        if path_recs:
            p = path_recs[0]
            path = {
                "node_ids": p["node_ids"],
                "node_names": p["node_names"],
                "node_types": p["node_types"],
                "rels": p["rels"],
                "hops": p["hops"],
            }

        # ── 3) Grounded citations from provenance store ───────────────
        prov_ids: list[str] = []
        if path:
            for nid in path["node_ids"]:
                prov_ids.extend(nodes_map.get(nid, {}).get("prov") or [])
        prov_ids = list(dict.fromkeys(prov_ids))  # dedupe, keep order
        citations = await _fetch_provenance(prov_ids)

        # ── 4) Summary: LLM if configured, deterministic otherwise ────
        if settings.llm_api_base:
            try:
                async for chunk in _llm_summary_stream(q, matched, path, citations):
                    yield f"data: {json.dumps({'type': 'tokens', 'text': chunk})}\n\n"
            except Exception as e:
                # Degrade to deterministic summary on any LLM failure
                fallback = _deterministic_summary(matched, path, citations)
                yield f"data: {json.dumps({'type': 'tokens', 'text': fallback})}\n\n"
        else:
            summary = _deterministic_summary(matched, path, citations)
            # Stream in small chunks so the UX matches the LLM path
            for i in range(0, len(summary), 24):
                yield f"data: {json.dumps({'type': 'tokens', 'text': summary[i:i+24]})}\n\n"

        yield f"data: {json.dumps({'type': 'citations', 'citations': citations, 'path': path})}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
