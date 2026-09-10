"""
TRACE unit tests — pure logic, no database or live stack required.
Covers (Phase 3 gaps): NLP relation precision on labeled samples, chat
candidate matching (incl. the loosened fuzzy matching + fail-closed behavior),
heuristic-edge suppression when a confirmed edge exists, priority score
grading of cross-case recurrence, graph canonicalization/reconciliation
purity, and document parser normalization.
Run inside the api container:
  docker exec trace-api python -m pytest /app/tests_e2e/unit -q
"""
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import pytest


# ══════════════════════════════════════════════════════════════════
# NLP relations — precision on small labeled samples + stress sentences
# ══════════════════════════════════════════════════════════════════
from app.nlp.relations import extract_relations

PAGE = [{"page": 1, "paragraphs": []}]


def _ents(*pairs):
    """Build entity rows anchored to paragraph 1."""
    return [
        {"entity_type": t, "value": v, "snippet": "", "page": 1, "paragraph": 1,
         "extractor": "test", "confidence": 0.9}
        for t, v in pairs
    ]


def _rels(sentence, ents):
    """Run relation extraction over one sentence with the given entities."""
    PAGE[0]["paragraphs"] = [sentence]
    entities = _ents(*ents)
    for e in entities:
        e["snippet"] = sentence
    relations, _ = extract_relations(PAGE, entities, use_llm_fallback=False)
    return relations


def test_transfer_between_accounts():
    s = "Bank account HDFC-XXXX-7741 transferred 5 lakh to account SBI-XXXX-3320."
    rels = _rels(s, [("BANK_ACCOUNT", "HDFC-XXXX-7741"), ("BANK_ACCOUNT", "SBI-XXXX-3320")])
    assert any(r["relation"] == "TRANSFERRED_TO" for r in rels), rels


def test_transfer_from_to_orders_head_tail():
    s = "Funds were transferred from SBI-XXXX-3320 to HDFC-XXXX-7741 last week."
    rels = _rels(s, [("BANK_ACCOUNT", "HDFC-XXXX-7741"), ("BANK_ACCOUNT", "SBI-XXXX-3320")])
    t = [r for r in rels if r["relation"] == "TRANSFERRED_TO"]
    assert t and t[0]["head_value"] == "SBI-XXXX-3320" and t[0]["tail_value"] == "HDFC-XXXX-7741", rels


def test_called_between_people():
    s = "Rohan Mehra called Priya Sharma eleven times in January."
    rels = _rels(s, [("PERSON", "Rohan Mehra"), ("PERSON", "Priya Sharma")])
    assert any(r["relation"] == "CALLED" and {r["head_value"], r["tail_value"]} ==
               {"Rohan Mehra", "Priya Sharma"} for r in rels), rels


def test_travelled_with_between_people():
    s = "Anita Desai travelled to Bengaluru with Rohan Mehra on Friday."
    rels = _rels(s, [("PERSON", "Anita Desai"), ("PERSON", "Rohan Mehra"), ("LOCATION", "Bengaluru")])
    tw = [r for r in rels if r["relation"] == "TRAVELLED_WITH"]
    assert tw and any({x["head_value"], x["tail_value"]} == {"Anita Desai", "Rohan Mehra"} for x in tw), rels
    # Person→city must be ASSOCIATED_WITH, never TRAVELLED_WITH
    assert all(not ({r["head_value"], r["tail_value"]} == {"Anita Desai", "Bengaluru"}
                    and r["relation"] == "TRAVELLED_WITH") for r in rels), rels


def test_no_relations_without_cue():
    s = "Rohan Mehra and Priya Sharma live in the same neighborhood as Anita Desai."
    rels = _rels(s, [("PERSON", "Rohan Mehra"), ("PERSON", "Priya Sharma"), ("PERSON", "Anita Desai")])
    assert rels == [], rels


def test_no_cross_paragraph_bleed():
    PAGE[0]["paragraphs"] = [
        "Rohan Mehra called Priya Sharma twice.",
        "Anita Desai met with Vikram Singh at the office.",
    ]
    ents = _ents(("PERSON", "Rohan Mehra"), ("PERSON", "Priya Sharma"),
                 ("PERSON", "Anita Desai"), ("PERSON", "Vikram Singh"))
    for e, snippet in zip(ents, PAGE[0]["paragraphs"] * 2):
        e["snippet"] = snippet
    relations, _ = extract_relations(PAGE, ents, use_llm_fallback=False)
    pairs = {frozenset((r["head_value"], r["tail_value"])) for r in relations}
    assert frozenset(("Rohan Mehra", "Anita Desai")) not in pairs
    assert frozenset(("Priya Sharma", "Vikram Singh")) not in pairs


def test_tricky_negation_under_generates_rather_than_guessing():
    # Cue present but the pair is nonsensical (person "transferring to" a city):
    # the extractor must NOT emit a relation for that pair.
    s = "The dossier says Vikram transferred documents to Bengaluru last spring."
    rels = _rels(s, [("PERSON", "Vikram"), ("LOCATION", "Bengaluru")])
    assert all(r["relation"] != "TRANSFERRED_TO" for r in rels), rels


def test_ambiguous_sentence_over_generation_is_bounded():
    # Known weakness: single-sentence co-occurrence + cues. Two cues in one
    # sentence must yield at most one relation per pair (priority ordering),
    # never duplicates.
    s = ("Records show Rohan called Priya and later travelled with her, and funds "
         "were moved between their accounts HDFC-XXXX-7741 and SBI-XXXX-3320.")
    rels = _rels(s, [("PERSON", "Rohan"), ("PERSON", "Priya"),
                     ("BANK_ACCOUNT", "HDFC-XXXX-7741"), ("BANK_ACCOUNT", "SBI-XXXX-3320")])
    pair_labels = [(r["head_value"], r["tail_value"], r["relation"]) for r in rels]
    assert len(pair_labels) == len(set(pair_labels)), rels


# ══════════════════════════════════════════════════════════════════
# Chat candidate matching — loosened fuzzy matching, fail-closed
# ══════════════════════════════════════════════════════════════════
from app.routers.chat import _extract_candidates, _match_nodes, FUZZY_THRESHOLD

NODES = [
    {"id": "PER-1", "label": "Fatima Khan", "aliases": ["F. Khan"]},
    {"id": "PER-2", "label": "Rohan Mehra", "aliases": ["R. Mehra", "Rohan M."]},
    {"id": "LOC-1", "label": "Bengaluru, Karnataka", "aliases": []},
    {"id": "BA-1", "label": "HDFC-XXXX-4521", "aliases": []},
    {"id": "PHN-1", "label": "+91-98765-43210", "aliases": []},
]


def _match(q):
    return _match_nodes(_extract_candidates(q), NODES)


def test_natural_lowercase_question_matches():
    # The audit's target example: no capitals, loose phrasing.
    matched, per = _match("how does khan connect to the warehouse guy")
    assert matched and matched[0]["id"] == "PER-1", (matched, per)


def test_lowercase_partial_names():
    matched, _ = _match("how does rohan connect to khan")
    ids = [m["id"] for m in matched]
    assert ids == ["PER-2", "PER-1"], ids


def test_identifier_without_separators():
    matched, _ = _match("any calls from 9876543210 recently")
    assert matched and matched[0]["id"] == "PHN-1", matched


def test_fail_closed_on_unknown_entities():
    matched, per = _match("how does zzzzq connect to qqqvv")
    assert matched == []
    assert all(x is None for x in per)


def test_gibberish_near_miss_does_not_match():
    # "khanx" vs "khan": token_set_ratio would score low; must fail closed.
    matched, per = _match("how does khanx connect to rohan mehra")
    ids = [m["id"] for m in matched]
    assert "PER-1" not in ids, (ids, per)
    assert "PER-2" in ids


def test_full_names_still_match_exactly():
    matched, _ = _match("How is Rohan Mehra connected to Fatima Khan?")
    ids = [m["id"] for m in matched]
    # Bigram candidates come first, so the canonical pair leads; unigram
    # candidates ("Rohan", "Khan") may repeat the same entities after them.
    assert ids[:2] == ["PER-2", "PER-1"], ids


def test_aliases_match_case_insensitively():
    matched, _ = _match("did f. khan know r. mehra")
    ids = [m["id"] for m in matched]
    assert ids == ["PER-1", "PER-2"], ids


def test_threshold_is_meaningful():
    assert 80 <= FUZZY_THRESHOLD <= 95


# ══════════════════════════════════════════════════════════════════
# Heuristic links — suppression when a confirmed edge exists
# ══════════════════════════════════════════════════════════════════
from app.graph.heuristics import compute_leads


def _n(i, t="PERSON"):
    return {"id": i, "name": i, "type": t}


def test_suppresses_lead_where_confirmed_edge_exists():
    nodes = [_n("A"), _n("B"), _n("SHARED", "PHONE")]
    edges = [{"source": "A", "target": "SHARED", "relation": "ASSOCIATED_WITH"},
             {"source": "B", "target": "SHARED", "relation": "ASSOCIATED_WITH"}]
    leads = compute_leads(nodes, edges)["edges"]
    # A and B share infrastructure but ALREADY have no direct edge → lead IS added
    assert any({l["source"], l["target"]} == {"A", "B"} for l in leads), leads


def test_no_lead_for_directly_connected_pair():
    nodes = [_n("A"), _n("B"), _n("S1", "PHONE"), _n("S2", "PHONE")]
    edges = [
        {"source": "A", "target": "S1", "relation": "ASSOCIATED_WITH"},
        {"source": "B", "target": "S1", "relation": "ASSOCIATED_WITH"},
        {"source": "A", "target": "S2", "relation": "ASSOCIATED_WITH"},
        {"source": "B", "target": "S2", "relation": "ASSOCIATED_WITH"},
        {"source": "A", "target": "B", "relation": "ASSOCIATED_WITH"},  # confirmed
    ]
    leads = compute_leads(nodes, edges)["edges"]
    assert not any({l["source"], l["target"]} == {"A", "B"} for l in leads), leads


def test_common_neighbors_jaccard_threshold():
    nodes = [_n("A"), _n("B"), _n("x"), _n("y")]
    edges = [{"source": "A", "target": x, "relation": "ASSOCIATED_WITH"} for x in ("x", "y")] + \
            [{"source": "B", "target": x, "relation": "ASSOCIATED_WITH"} for x in ("x", "y")]
    leads = compute_leads(nodes, edges)["edges"]
    cn = [l for l in leads if l["kind"] == "common_neighbors"]
    assert cn and cn[0]["score"] >= 0.34, leads


def test_indirect_funds_flow_detected_and_suppressed_by_direct_edge():
    base_nodes = [_n("BA1", "BANK_ACCOUNT"), _n("BA2", "BANK_ACCOUNT"), _n("BA3", "BANK_ACCOUNT")]
    chain = [{"source": "BA1", "target": "BA2", "relation": "TRANSFERRED_TO"},
             {"source": "BA2", "target": "BA3", "relation": "TRANSFERRED_TO"}]
    leads = compute_leads(base_nodes, chain)["edges"]
    assert any(l["kind"] == "indirect_funds_flow" and {l["source"], l["target"]} == {"BA1", "BA3"}
               for l in leads), leads
    # Add the direct confirmed edge → lead must disappear
    direct = chain + [{"source": "BA1", "target": "BA3", "relation": "TRANSFERRED_TO"}]
    leads2 = compute_leads(base_nodes, direct)["edges"]
    assert not any(l["kind"] == "indirect_funds_flow" for l in leads2), leads2


def test_leads_are_never_marked_confirmed():
    nodes = [_n("A"), _n("B"), _n("SHARED", "PHONE")]
    edges = [{"source": "A", "target": "SHARED", "relation": "ASSOCIATED_WITH"},
             {"source": "B", "target": "SHARED", "relation": "ASSOCIATED_WITH"}]
    leads = compute_leads(nodes, edges)["edges"]
    assert all(l.get("kind") != "confirmed" for l in leads)


# ══════════════════════════════════════════════════════════════════
# Priority score — graded cross-case recurrence
# ══════════════════════════════════════════════════════════════════
from app.graph.priority import _cross_case_norm, RECURRENCE_CAP, _explain


def test_recurrence_grading_is_graded_not_binary():
    assert _cross_case_norm(1) == 0.0
    assert 0.0 < _cross_case_norm(2) < _cross_case_norm(3) < _cross_case_norm(4) < 1.0
    assert _cross_case_norm(2) == 0.25


def test_recurrence_saturates_at_cap():
    # Linear ramp over CAP additional cases, then saturates:
    # 2 cases → 0.25 … 5 cases (CAP+1) → 1.0
    assert _cross_case_norm(RECURRENCE_CAP) == 0.75
    assert _cross_case_norm(RECURRENCE_CAP + 1) == 1.0
    assert _cross_case_norm(RECURRENCE_CAP + 10) == 1.0


def test_recurrence_zero_for_single_case():
    assert _cross_case_norm(1) == 0.0
    assert _cross_case_norm(0) == 0.0


def test_explanation_mentions_case_count_and_is_neutral():
    bullets = _explain(0.5, 0.6, 5, True)
    joined = " ".join(bullets).lower()
    assert "5 case(s)" in joined
    assert not any(w in joined for w in ("criminal", "guilt", "arrest"))


# ══════════════════════════════════════════════════════════════════
# Graph canonicalization — union-find purity + reconciliation logic
# ══════════════════════════════════════════════════════════════════
from app.graph.service import build_canonicalization, normalize_entities, _global_entity_id


def test_union_find_resolves_transitive_merges():
    canon = build_canonicalization([
        {"primary_entity_id": "b", "merged_entity_id": "a"},
        {"primary_entity_id": "c", "merged_entity_id": "b"},
    ])
    assert canon["a"] == canon["b"] == canon["c"]
    assert canon["a"] == "a"  # lexicographic root


def test_canonicalization_is_deterministic():
    merges = [{"primary_entity_id": "x", "merged_entity_id": "y"},
              {"primary_entity_id": "p", "merged_entity_id": "q"}]
    assert build_canonicalization(merges) == build_canonicalization(list(reversed(merges)))


def test_normalize_entities_merges_aliases_and_provenance():
    rows = [
        {"entity_or_edge_id": "e1", "entity_type": "PERSON", "value": "R. Mehra",
         "provenance_id": "p1", "case_id": "c1"},
        {"entity_or_edge_id": "e2", "entity_type": "PERSON", "value": "Rohan Mehra",
         "provenance_id": "p2", "case_id": "c2"},
    ]
    canon = build_canonicalization([{"primary_entity_id": "e2", "merged_entity_id": "e1"}])
    value_of = {"e1": "R. Mehra", "e2": "Rohan Mehra"}
    nodes = normalize_entities(rows, canon, value_of)
    assert len(nodes) == 1
    node = next(iter(nodes.values()))
    assert node["aliases"] == {"R. Mehra", "Rohan Mehra"}
    assert node["case_ids"] == {"c1", "c2"}
    assert node["provenance_ids"] == {"p1", "p2"}
    # Display name = longest alias
    assert node["name"] == "Rohan Mehra"


def test_global_entity_id_stable_across_case():
    assert _global_entity_id("PERSON", "rohan mehra") == _global_entity_id("PERSON", "Rohan Mehra")
    assert _global_entity_id("PERSON", "rohan mehra") != _global_entity_id("ORG", "rohan mehra")


# ══════════════════════════════════════════════════════════════════
# Parsers — normalization invariants (belt & braces)
# ══════════════════════════════════════════════════════════════════
from app.ingestion.parsers import parse_csv, parse_txt, parse_json


def test_csv_columns_normalized():
    text, pages = parse_csv(b"a,b\n1,2\n3,4\n")
    assert "a: 1" in text and "b: 4" in text
    assert pages[0]["page"] == 1


def test_json_records_list():
    text, _ = parse_json(b'[{"name": "X", "phone": "123"}]')
    assert "name: X" in text


def test_txt_paragraph_splitting():
    text, pages = parse_txt("para one\n\npara two".encode())
    assert len(pages[0]["paragraphs"]) == 2
