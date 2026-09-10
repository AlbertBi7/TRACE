"""
TRACE — Relation Extraction (Milestone 3)
Deterministic, pattern-based extraction of the four canonical relations:
CALLED, TRANSFERRED_TO, TRAVELLED_WITH, ASSOCIATED_WITH.
Runs per paragraph over entities found in that same paragraph (co-occurrence
window = one sentence — no document-wide guessing). Direction follows the
sentence: for transfers, an explicit "from A to B" overrides mention order.
Below a confidence threshold, an optional strictly-scoped LLM classifier
(single sentence → one of the four labels) may be consulted; without an LLM
configured, the deterministic result stands unchanged.
"""

import re

from app.nlp.llm_fallback import classify_relation

LLM_CONFIDENCE_THRESHOLD = 0.6

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

CALLED_RE = re.compile(
    r"\b(call(?:ed|s)?|phoned|rang|telephoned|contacted|spoke\s+(?:to|with))\b", re.I
)
TRANSFER_RE = re.compile(
    r"\b(transfer(?:red|s)?|wire[ds]?|sent|moved|deposited|paid|remitted)\b", re.I
)
TRAVEL_RE = re.compile(
    r"\b(travel(?:led|ed|s)?|flew|drove|went|departed|arrived|accompanied)\b", re.I
)
ASSOC_RE = re.compile(
    r"\b(associated\s+with|partner(?:ed)?\s+with|worked\s+(?:for|with|at)|employee\s+of|"
    r"director\s+of|owner\s+of|member\s+of|met\s+with|linked\s+to|affiliated\s+with|"
    r"known\s+associate|account\s+holder|registered\s+owner|residence\s+at|"
    r"occupies|owns|operates|uses)\b",
    re.I,
)
# Explicit directional transfer: "from X to Y"
FROM_TO_RE = re.compile(r"\bfrom\s+(.+?)\s+to\b", re.I)

PRIORITY = {"TRANSFERRED_TO": 0, "CALLED": 1, "TRAVELLED_WITH": 2, "ASSOCIATED_WITH": 3}

# Person/org-ish types come first when ordering head/tail by type
TYPE_PRIORITY = {"PERSON": 0, "ORG": 1, "LOCATION": 2, "PHONE": 3, "BANK_ACCOUNT": 4, "VEHICLE": 5}

# Same-type structural pairs never form a meaningful relation
NO_SAME_TYPE = {"PHONE", "BANK_ACCOUNT", "VEHICLE", "LOCATION"}


def _sentences(para: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT_RE.split(para) if s.strip()]


def _relation_confidence(cue_count: int, sentence_len: int) -> float:
    """Deterministic confidence: more distinct cue families, shorter sentence → higher."""
    base = {1: 0.55, 2: 0.7, 3: 0.8}.get(cue_count, 0.65)
    if sentence_len > 220:
        base -= 0.1
    return round(max(0.35, min(0.9, base)), 2)


def _cues(sentence: str) -> list[str]:
    cues = []
    if TRANSFER_RE.search(sentence):
        cues.append("TRANSFERRED_TO")
    if CALLED_RE.search(sentence):
        cues.append("CALLED")
    if TRAVEL_RE.search(sentence):
        cues.append("TRAVELLED_WITH")
    if ASSOC_RE.search(sentence):
        cues.append("ASSOCIATED_WITH")
    return cues


def _order_pair(head: dict, tail: dict, sentence: str) -> tuple[dict, dict]:
    """
    Choose head/tail direction:
      - TRANSFERRED_TO with explicit 'from A to B': A is head if matched.
      - Otherwise: person/org-ish type first, then order of appearance.
    """
    m = FROM_TO_RE.search(sentence)
    if m:
        src = m.group(1)
        if head["value"] in src and head["value"] not in tail["value"]:
            return head, tail
        if tail["value"] in src and tail["value"] not in head["value"]:
            return tail, head
    if TYPE_PRIORITY.get(head["entity_type"], 6) != TYPE_PRIORITY.get(tail["entity_type"], 6):
        if TYPE_PRIORITY.get(head["entity_type"], 6) > TYPE_PRIORITY.get(tail["entity_type"], 6):
            return tail, head
        return head, tail
    # Same priority: order of appearance in the sentence
    if sentence.lower().find(tail["value"].lower()) < sentence.lower().find(head["value"].lower()):
        return tail, head
    return head, tail


def _pair_label(cue_relation: str, a: dict, b: dict, sentence: str) -> str | None:
    """
    Pick the correct relation for a SPECIFIC pair given its endpoint types.
    The sentence-level cue is just a hint; an account 'transferring to' a
    person is not a financial edge, and 'travelled to Bengaluru' does not make
    a person TRAVELLED_WITH a city. Returns None to skip the pair.
    """
    h, t = a["entity_type"], b["entity_type"]
    money = {"BANK_ACCOUNT"}
    peopleish = {"PERSON", "ORG"}

    if cue_relation == "TRANSFERRED_TO":
        if h in money and t in money:
            return "TRANSFERRED_TO"
        if h in money and t in peopleish:
            return None  # "transferred funds to Vikram" names the sender, not a transfer edge
        if h in peopleish and t in money:
            # Account holder / originator association — confirmed by transfer context
            return "ASSOCIATED_WITH"
        return None

    if cue_relation == "CALLED":
        if h == "PHONE" and t == "PHONE":
            return "CALLED"  # call records between numbers
        if {h, t} == {"PERSON", "PHONE"}:
            return "CALLED"
        if h in peopleish and t in peopleish:
            return "CALLED"  # 'contacted' between people
        return None

    if cue_relation == "TRAVELLED_WITH":
        if h == "PERSON" and t == "PERSON":
            return "TRAVELLED_WITH"
        if {h, t} == {"PERSON", "LOCATION"}:
            return "ASSOCIATED_WITH"  # travel to a place associates, not travels-with
        return None

    if cue_relation == "ASSOCIATED_WITH":
        return "ASSOCIATED_WITH"

    return None


def extract_relations(
    pages: list[dict],
    entities: list[dict],
    use_llm_fallback: bool = True,
) -> tuple[list[dict], list[dict]]:
    """
    Build pairwise relations from entities co-occurring in the same sentence.

    Returns (relations, llm_calls):
      relations: {relation, head_value, tail_value, snippet, page, paragraph,
                  extractor, confidence}
      llm_calls: audit rows for every LLM consultation (even when the model
                 declines or is unavailable — kept for extraction_log)
    """
    relations: list[dict] = []
    llm_calls: list[dict] = []

    # Group entities by (page, paragraph) — the co-occurrence window
    by_para: dict[tuple[int, int], list[dict]] = {}
    for e in entities:
        by_para.setdefault((e["page"], e["paragraph"]), []).append(e)

    for (page_no, para_no), ents in by_para.items():
        if len(ents) < 2:
            continue
        snippet = ents[0]["snippet"]
        for sentence in _sentences(snippet):
            present = [e for e in ents if sentence.lower().find(e["value"].lower()) >= 0]
            if len(present) < 2:
                continue

            cues = _cues(sentence)
            if not cues:
                continue

            relation = sorted(cues, key=lambda r: PRIORITY[r])[0]
            conf = _relation_confidence(len(cues), len(sentence))

            for i, head in enumerate(present):
                for tail in present[i + 1:]:
                    if head["entity_type"] == tail["entity_type"] and head["entity_type"] in NO_SAME_TYPE:
                        # Same-type structural pairs are only meaningful for
                        # specific cues: phone↔phone CALLED (call records) and
                        # account↔account TRANSFERRED_TO ("transferred from X
                        # to Y"). Skipping unconditionally here made the
                        # money×money branch of _pair_label unreachable, so
                        # extracted data could never contain account-to-account
                        # transfer edges.
                        meaningful = (head["entity_type"] == "PHONE" and relation == "CALLED") or (
                            head["entity_type"] == "BANK_ACCOUNT" and relation == "TRANSFERRED_TO"
                        )
                        if not meaningful:
                            continue

                    # Sort so the "first" of the pair respects type/appearance ordering
                    a, b = _order_pair(head, tail, sentence)

                    # Type-aware label: skip pairs the cue doesn't fit
                    label = _pair_label(relation, a, b, sentence)
                    if label is None:
                        continue

                    relations.append({
                        "relation": label,
                        "head_value": a["value"],
                        "tail_value": b["value"],
                        "snippet": sentence,
                        "page": page_no,
                        "paragraph": para_no,
                        "extractor": "pattern.relation",
                        "confidence": conf,
                    })

                    # Below-threshold pairs are also queued for the scoped LLM
                    # classifier (when configured) as an independent second
                    # opinion — its accepted labels are added as extra rows by
                    # resolve_llm_calls; the deterministic row is always kept.
                    if conf < LLM_CONFIDENCE_THRESHOLD and use_llm_fallback:
                        llm_calls.append({
                            "relation": label,
                            "head_value": a["value"],
                            "tail_value": b["value"],
                            "sentence": sentence,
                            "page": page_no,
                            "paragraph": para_no,
                            "deterministic_confidence": conf,
                        })

    return relations, llm_calls


async def resolve_llm_calls(llm_calls: list[dict]) -> list[dict]:
    """
    Consult the scoped LLM classifier for below-threshold pairs (async).
    Returns additional relations where the model confidently picked a label
    other than NONE. Every consultation is logged by the caller.
    """
    extra: list[dict] = []
    for call in llm_calls:
        result = await classify_relation(call["sentence"], call["head_value"], call["tail_value"])
        if result and result["relation"] != "NONE" and result["confidence"] >= 0.6:
            extra.append({
                "relation": result["relation"],
                "head_value": call["head_value"],
                "tail_value": call["tail_value"],
                "snippet": call["sentence"],
                "page": call["page"],
                "paragraph": call["paragraph"],
                "extractor": "llm.relation_classifier",
                "confidence": result["confidence"],
            })
    return extra
