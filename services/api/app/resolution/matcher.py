"""
TRACE — Entity Resolution Matcher (Milestone 4)
Deterministic candidate generation over extraction_log entities:
  1. Fuzzy name matching (RapidFuzz token_sort_ratio) for same-type entities.
  2. Shared-attribute matching: PERSON nodes referencing the exact same
     PHONE / BANK_ACCOUNT / VEHICLE value are near-certainly the same person.
Produces merge SUGGESTIONS with confidence scores — never applied silently.
"""

import re
from rapidfuzz import fuzz

from app.db.postgres import get_pool

# ─── Tunables ─────────────────────────────────────────────────────────
FUZZY_THRESHOLD = 85.0          # token_sort_ratio for same-type names
SHARED_ATTR_CONFIDENCE = 0.95   # exact shared phone/account ⇒ very high
FUZZY_HIGH_CONF = 0.9
FUZZY_LOW_CONF = 0.7

NAME_LIKE_TYPES = {"PERSON", "ORG", "LOCATION"}

HONORIFIC_RE = re.compile(r"^(mr|mrs|ms|dr|shri|smt)\.?\s+", re.I)


def _norm_name(name: str) -> str:
    name = HONORIFIC_RE.sub("", name.strip())
    return re.sub(r"\s+", " ", name).lower()


def _initials_match(a: str, b: str) -> bool:
    """'R. Mehra' vs 'Rohan Mehra' → True; 'R. Mehra' vs 'Priya Mehra' → False."""
    fa, fb = a.split(), b.split()
    if len(fa) == 2 and len(fb) == 2:
        first_a, rest_a = fa
        first_b, rest_b = fb
        if rest_a == rest_b:
            short, full = (first_a, first_b) if len(first_a) < len(first_b) else (first_b, first_a)
            if short.endswith(".") and full.startswith(short[0]):
                return True
    return False


def _fuzzy_score(a: str, b: str) -> float:
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if _initials_match(na, nb):
        return FUZZY_HIGH_CONF
    score = fuzz.token_sort_ratio(na, nb) / 100.0
    # Penalize very short strings where high ratios are less meaningful
    if len(na) < 6 or len(nb) < 6:
        score -= 0.1
    return round(score, 3)


def _distinct_values(rows) -> dict[str, str]:
    """entity_id → most common surface value (by row count)."""
    counts: dict[str, dict[str, int]] = {}
    for r in rows:
        counts.setdefault(r["entity_or_edge_id"], {})
        counts[r["entity_or_edge_id"]][r["value"]] = counts[r["entity_or_edge_id"]].get(r["value"], 0) + 1
    return {eid: max(vals, key=vals.get) for eid, vals in counts.items()}


def _group_entities_by_type(entity_rows) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in entity_rows:
        groups.setdefault(r["entity_type"], []).append(r)
    return groups


async def suggest_merges(case_id: str) -> list[dict]:
    """
    Generate merge suggestions for one case from extraction_log entities.
    Idempotent: skips pairs already recorded in entity_merges.
    """
    pool = await get_pool()

    entity_rows = await pool.fetch(
        """SELECT DISTINCT entity_or_edge_id, entity_type, value
           FROM extraction_log e
           JOIN documents d ON d.id = e.document_id
           WHERE d.case_id = $1 AND e.head_entity_id = '' AND e.value <> ''""",
        case_id,
    )

    existing = set()
    for r in await pool.fetch(
        "SELECT primary_entity_id, merged_entity_id, status FROM entity_merges WHERE case_id = $1",
        case_id,
    ):
        # Only ACCEPTED decisions suppress new suggestions. 'suggested' rows are
        # refreshed by the upsert below, and 'undone' rows are re-suggested so an
        # investigator can change their mind (history is preserved via status).
        if r["status"] == "accepted":
            existing.add((r["primary_entity_id"], r["merged_entity_id"]))
            existing.add((r["merged_entity_id"], r["primary_entity_id"]))

    suggestions: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()

    def add(primary: str, merged: str, method: str, confidence: float, rationale: dict):
        key = (primary, merged) if primary < merged else (merged, primary)
        if key in seen_pairs or key in existing or primary == merged:
            return
        seen_pairs.add(key)
        suggestions.append({
            "primary_entity_id": key[0],
            "merged_entity_id": key[1],
            "method": method,
            "confidence": confidence,
            "rationale": rationale,
        })

    # ── 1) Shared-attribute identity: same phone/account/vehicle on PERSONs ──
    attr_rows = await pool.fetch(
        """SELECT DISTINCT e.entity_or_edge_id, e.entity_type, e.value
           FROM extraction_log e
           JOIN documents d ON d.id = e.document_id
           WHERE d.case_id = $1 AND e.entity_type IN ('PHONE','BANK_ACCOUNT','VEHICLE')""",
        case_id,
    )
    attr_values = {(r["entity_type"], r["value"].lower()) for r in attr_rows}

    # Person→attribute association from direct co-occurrence: a PERSON mentioned
    # in the same paragraph as a PHONE/BANK_ACCOUNT/VEHICLE is treated as holding
    # that attribute (identity signal — independent of relation-cue vocabulary).
    # Grouping key includes document_id — (page, paragraph) alone would merge
    # same-numbered paragraphs across different documents.
    para_rows = await pool.fetch(
        """SELECT DISTINCT e.document_id, e.page, e.paragraph, e.entity_or_edge_id, e.entity_type
           FROM extraction_log e
           JOIN documents d ON d.id = e.document_id
           WHERE d.case_id = $1 AND e.head_entity_id = '' AND e.value <> ''""",
        case_id,
    )
    attr_types = {"PHONE", "BANK_ACCOUNT", "VEHICLE"}
    by_para: dict[tuple[str, int, int], list] = {}
    for r in para_rows:
        by_para.setdefault((str(r["document_id"]), r["page"], r["paragraph"]), []).append(r)
    person_attrs: dict[str, set[str]] = {}
    for ents in by_para.values():
        pids = [e["entity_or_edge_id"] for e in ents if e["entity_type"] == "PERSON"]
        aids = [e["entity_or_edge_id"] for e in ents if e["entity_type"] in attr_types]
        for pid in pids:
            person_attrs.setdefault(pid, set()).update(aids)

    # Also fold in relation-derived links (person -[ASSOCIATED_WITH]-> attribute)
    rel_rows = await pool.fetch(
        """SELECT DISTINCT e.head_entity_id, e.tail_entity_id, te.entity_type
           FROM extraction_log e
           JOIN documents d ON d.id = e.document_id
           LEFT JOIN extraction_log te ON te.entity_or_edge_id = e.tail_entity_id
                AND te.head_entity_id = '' AND te.value <> ''
           WHERE d.case_id = $1 AND e.head_entity_id <> ''""",
        case_id,
    )
    for r in rel_rows:
        if r["entity_type"] in attr_types:
            person_attrs.setdefault(r["head_entity_id"], set()).add(r["tail_entity_id"])

    persons = [p for p in _group_entities_by_type(entity_rows).get("PERSON", [])]
    for i, p1 in enumerate(persons):
        for p2 in persons[i + 1:]:
            shared = person_attrs.get(p1["entity_or_edge_id"], set()) & person_attrs.get(
                p2["entity_or_edge_id"], set()
            )
            if shared:
                add(
                    p1["entity_or_edge_id"], p2["entity_or_edge_id"],
                    "shared_attribute", SHARED_ATTR_CONFIDENCE,
                    {"shared_attribute_ids": sorted(shared), "reason": "exact shared phone/account/vehicle reference"},
                )

    # ── 2) Fuzzy name matching within same type ──
    for etype, rows in _group_entities_by_type(entity_rows).items():
        if etype not in NAME_LIKE_TYPES:
            continue
        values = _distinct_values(rows)
        ids = list(values.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = values[ids[i]], values[ids[j]]
                score = _fuzzy_score(a, b)
                if score * 100 >= FUZZY_THRESHOLD:
                    primary, merged = sorted([ids[i], ids[j]])  # stable canonical = lexicographic
                    add(
                        primary, merged, "fuzzy", round(score, 3),
                        {"value_a": a, "value_b": b, "reason": f"token_sort_ratio >= {FUZZY_THRESHOLD}"},
                    )

    # Persist as suggestions (idempotent upsert). Re-suggesting an 'undone'
    # pair revives it as 'suggested' (suggested_at refreshed); accepted rows
    # are never downgraded. Row history is never deleted.
    for s in suggestions:
        await pool.execute(
            """INSERT INTO entity_merges
                   (case_id, primary_entity_id, merged_entity_id, method, confidence, status)
               VALUES ($1, $2, $3, $4, $5, 'suggested')
               ON CONFLICT (case_id, primary_entity_id, merged_entity_id)
               DO UPDATE SET confidence = EXCLUDED.confidence, method = EXCLUDED.method,
                             status = 'suggested', suggested_at = NOW()
               WHERE entity_merges.status IN ('suggested', 'undone')""",
            case_id,
            s["primary_entity_id"],
            s["merged_entity_id"],
            s["method"],
            s["confidence"],
        )

    return suggestions
