"""
TRACE — Entity Extraction (Milestone 3)
Deterministic pipeline:
  1. Regex/structural patterns for PHONE, BANK_ACCOUNT, VEHICLE (high precision).
  2. spaCy NER for PERSON, ORG, LOCATION — skipping spans already claimed by regex.
Every result carries the verbatim paragraph snippet + page/paragraph numbers so
each extraction is traceable to its source location.
No GNN, no opaque models: regex + off-the-shelf NER only.
"""

import re

from app.nlp.spacy_model import get_nlp

# ─── Regex patterns (high-precision, structural identifiers) ─────────
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(\d{2,4}\)[-.\s]?)?\d{3,5}[-.\s]\d{3,6}(?:[-.\s]\d{2,6})?(?!\d)"
)
# Matches 'HDFC-XXXX-4521', 'ACCT 12345678', 'account no. 5577-8899-0011', IBAN-ish
ACCOUNT_RE = re.compile(
    r"(?:(?:A/C|ACCT|ACCOUNT)(?:\s+(?:NO|NUMBER|NOS?))?\s*[:.]?\s*)([A-Z0-9]{6,}(?:-XXXX-[A-Z0-9]{2,6})?)"
    r"|([A-Z]{3,6}-XXXX-[A-Z0-9]{2,6})"
    r"|\b([A-Z]{2}\d{2}[A-Z0-9]{10,26})\b"
)
# Indian-format plates like MH-02-AB-1234 / DL 01 CD 5678
VEHICLE_RE = re.compile(
    r"\b([A-Z]{2}[-\s]\d{1,2}[-\s][A-Z]{1,3}[-\s]\d{3,4})\b"
)

# spaCy label → TRACE entity type
NER_LABEL_MAP = {"PERSON": "PERSON", "ORG": "ORG", "GPE": "LOCATION", "LOC": "LOCATION"}

# Noise filters for NER hits — expanded to cover form-label leakage
ORG_BLOCKLIST = re.compile(
    r"\b(bank|police|court|department|ministry|bureau|team|case|unit|report|complainant|subject|accused|victim|witness|informant|fir|police station|ps|district|case type|date of occurrence|alibi corroboration|investigation report)\b",
    re.I,
)

# Header / form-label blocklist (all-caps headers and FIR table labels)
HEADER_LABEL_BLOCKLIST = re.compile(
    r"\b(complainant|subject|accused|victim|witness|informant|fir|police station|ps|district|case type|date of occurrence|alibi corroboration|investigation report)\b",
    re.I,
)

# Regex to split conjoined spans like "Rani, Anju" or "Anju and Anu" or "Rani & Anju"
CONJOINED_SPLIT_RE = re.compile(r"\s*(?:,|and|&)\s*", re.I)

# Words to strip when they collocate as label suffix/prefix on a person name
# e.g., "Geetha Prabhakar Subject" -> "Geetha Prabhakar", "Prabhakar Case" -> "Prabhakar"
LABEL_STRIP_WORDS = [
    "complainant", "subject", "accused", "victim", "witness", "informant",
    "fir", "police station", "ps", "district", "case type", "case",
    "date of occurrence", "alibi corroboration", "investigation report",
]

# ─── Contextual PERSON vs LOCATION disambiguation ─────────────────
LOCATION_INDICATORS = {
    "junction", "quarry", "depot", "road", "street", "estate", "district",
    "station", "outskirts", "colony", "nagar", "town", "city", "village",
    "bridge", "highway", "hall", "ps", "court",
}

LOCATION_PREPOSITIONS_RE = re.compile(
    r"\b(?:at|near|in|to|from|towards|through|around|heading\s+to|located\s+in|outside)\s+$",
    re.IGNORECASE,
)

PERSON_INDICATORS_RE = re.compile(
    r"\b(?:spoke\s+to|called|travelled\s+with|interrogated|questioned|met\s+with|interviewed|driver|conductor|operator)\s+$",
    re.IGNORECASE,
)


def refine_entity_type(val: str, initial_type: str, sentence_prefix: str) -> str:
    """
    Refines PERSON vs LOCATION using surrounding context and entity tokens.
    Deterministic, no LLM.
    """
    lower_val = val.lower()
    tokens = set(lower_val.split())

    # 1. Indicator keyword override (strong morphological cue)
    if tokens & LOCATION_INDICATORS:
        return "LOCATION"

    # 2. Person vs location preposition cues — person takes precedence over generic "to"
    is_person_cue = bool(PERSON_INDICATORS_RE.search(sentence_prefix))
    is_location_cue = bool(LOCATION_PREPOSITIONS_RE.search(sentence_prefix) or re.search(r"\b(?:at|near|in|to|from|towards|through|around|heading\s+to|located\s+in|outside)\s+the\s+$", sentence_prefix, re.I))

    if is_person_cue and initial_type in ("LOCATION", "GPE", "ORG"):
        return "PERSON"
    # If both cues present (e.g., "spoke to X" contains "to"), person cue wins — do not flip PERSON to LOCATION
    if is_location_cue and initial_type in ("PERSON", "ORG"):
        if is_person_cue:
            return initial_type
        return "LOCATION"

    # 3. Standardize GPE -> LOCATION
    if initial_type in ("GPE", "LOC"):
        return "LOCATION"

    return initial_type


# ─── Indian toponymic suffixes / gazetteer fallback ──────────────
INDIAN_LOCATION_SUFFIXES = (
    "kad", "puzha", "puram", "nagar", "wadi", "pet", "peth", "giri",
    "halli", "kodu", "ur", "oor", "patnam", "bad", "kot", "garh",
    "junction", "estate", "quarry", "colony",
)

PERSON_PREFIXES = (
    "mr", "mrs", "ms", "dr", "shri", "smt", "inspector", "si", "asi",
    "constable", "driver", "operator", "advocate", "conductor",
)


def apply_toponymic_rules(surface: str, current_type: str) -> str:
    lower = surface.lower().strip()
    for suffix in INDIAN_LOCATION_SUFFIXES:
        if lower.endswith(suffix) and len(lower) > len(suffix) + 2:
            return "LOCATION"
    for prefix in PERSON_PREFIXES:
        if lower.startswith(prefix + " "):
            return "PERSON"
    return current_type


# ─── Explicit procedural legal roles (human-stated only, no inference) ─
VALID_PROCEDURAL_ROLES = {
    "suspect", "accused", "victim", "witness",
    "complainant", "informant", "person_of_interest",
}

HEADER_ROLE_PATTERNS = [
    (re.compile(r"\bComplainant\s*[:\-]\s*([A-Za-z\s]+)", re.IGNORECASE), "complainant"),
    (re.compile(r"\b(?:Subject|Missing(?:\s+Person)?)\s*[:\-]\s*([A-Za-z\s]+)", re.IGNORECASE), "victim"),
    (re.compile(r"\b(?:Accused|Suspect)\s*[:\-]\s*([A-Za-z\s]+)", re.IGNORECASE), "suspect"),
    (re.compile(r"\bWitness(?:\s+Name)?\s*[:\-]\s*([A-Za-z\s]+)", re.IGNORECASE), "witness"),
]

# Inline: role + Title-Case name (1-3 words), role case-insensitive but name must be Title-Case to avoid greedy lower-case capture
INLINE_ROLE_PATTERN = re.compile(
    r"\b(?i:(suspect|accused|victim|witness|informant|complainant))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b",
)


def extract_procedural_roles(text: str, detected_persons: list[dict]) -> dict[str, str]:
    """
    Scans paragraph text for explicit role assignments.
    Returns mapping of normalized person name -> role (e.g. {'georgekutty': 'suspect'}).
    Deterministic, no prediction.
    """
    role_assignments: dict[str, str] = {}
    # 1. Check form header patterns
    for pattern, role in HEADER_ROLE_PATTERNS:
        match = pattern.search(text)
        if match:
            raw_name = match.group(1).strip().lower()
            # Clean raw_name similarly to surface normalization for matching
            raw_name_clean = re.sub(r"\s+", " ", raw_name).strip()
            for p in detected_persons:
                p_low = p["value"].lower()
                # Fuzzy containment: either contains or is contained
                if p_low in raw_name_clean or raw_name_clean in p_low:
                    role_assignments[p_low] = role
    # 2. Check inline narrative cues — exact name match only (no fuzzy) to avoid spillover
    for match in INLINE_ROLE_PATTERN.finditer(text):
        role = match.group(1).lower()
        name = match.group(2).strip().lower()
        name_clean = re.sub(r"\s+", " ", name).strip()
        if role in VALID_PROCEDURAL_ROLES:
            for p in detected_persons:
                p_low = p["value"].lower()
                if p_low == name_clean:
                    role_assignments[p_low] = role
    return role_assignments

# ─── Centralized surface normalization (prevents duplicate entity_ids) ─
TITLE_PREFIX_RE = re.compile(
    r"^(?:mr|mrs|ms|dr|shri|smt|inspector|sub-inspector|si|ig|accused|victim|witness|suspect)\.?\s+",
    re.IGNORECASE,
)
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?\'\"\s]+$")
LEADING_PUNCT_RE = re.compile(r"^[.,;:!?\'\"\s]+")


def clean_entity_surface(raw_val: str, entity_type: str) -> str:
    """
    Normalize entity surface before hashing/dedup:
      - strip leading/trailing punctuation/whitespace
      - for PERSON, strip honorifics/titles (Mr., SI, suspect, etc.)
      - collapse internal whitespace
    Deterministic, no inference.
    """
    val = raw_val.strip()
    val = LEADING_PUNCT_RE.sub("", val)
    val = TRAILING_PUNCT_RE.sub("", val)
    if entity_type == "PERSON":
        val = TITLE_PREFIX_RE.sub("", val)
        val = LEADING_PUNCT_RE.sub("", val)
        val = TRAILING_PUNCT_RE.sub("", val)
    val = re.sub(r"\s+", " ", val).strip()
    return val


def _strip_label_collocations(val: str, entity_type: str) -> str:
    """
    Strip leading/trailing label words that collocate on person names
    due to FIR table layout, e.g., "Geetha Prabhakar Subject" -> "Geetha Prabhakar".
    Iteratively removes phrases from LABEL_STRIP_WORDS at either end.
    """
    original = val
    # Sort phrases longest first so "police station" beats "ps"
    phrases = sorted(LABEL_STRIP_WORDS, key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        low = val.lower()
        for phrase in phrases:
            pl = phrase.lower()
            # leading phrase + space
            if low == pl:
                return ""
            if low.startswith(pl + " "):
                val = val[len(phrase):].lstrip(" ,;:.-")
                val = clean_entity_surface(val, entity_type)
                changed = True
                break
            if low.endswith(" " + pl):
                val = val[: -len(phrase)].rstrip(" ,;:.-")
                val = clean_entity_surface(val, entity_type)
                changed = True
                break
    return val


def _is_header_noise(val: str) -> bool:
    """All-caps header or form-label leakage should be discarded."""
    # 1) All-caps header: e.g., "RECORDED & ALIBI CORROBORATION"
    if val.isupper() and len(val.split()) > 1:
        return True
    # 2) Form / table label blocklist
    if HEADER_LABEL_BLOCKLIST.search(val):
        # But allow if after stripping label collocations the remainder is a clean person
        # The caller should try stripping first; this is fallback for pure labels
        # like "Complainant" alone -> discard
        stripped = _strip_label_collocations(val, "PERSON")
        if not stripped or stripped.lower() == val.lower():
            return True
        # If stripping reduces to a shorter value, let caller use stripped instead of discarding
        # So we don't discard here if stripping would salvage a name
        # Check if val is exactly a label phrase -> discard
        low = val.strip().lower()
        for phrase in LABEL_STRIP_WORDS:
            if low == phrase.lower():
                return True
        # If val contains label as major component and is short, treat as noise
        # e.g., "Rajakkad PS FIR" contains two labels; after stripping it may leave "Rajakkad"
        # That's handled by caller stripping; here we just flag if the whole val is label-heavy
        # For now, only discard if the stripped version is empty or still matches blocklist without improvement
    return False


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _char_pos_to_para(text: str, start: int, end: int) -> tuple[int, int]:
    """Map a character span in the paragraph text to (paragraph_no, offset) — para is 1-based."""
    return 0, 0  # paragraph index is resolved by the caller per-paragraph


def extract_entities(pages: list[dict]) -> list[dict]:
    """
    Extract entities from parsed pages: [{page, paragraphs: [str, ...]}]
    Returns rows: {entity_type, value, snippet, page, paragraph, extractor, confidence}
    """
    entities: list[dict] = []
    nlp = get_nlp()

    for page in pages:
        page_no = page.get("page", 0)
        for para_no, para in enumerate(page.get("paragraphs", []), start=1):
            text = _clean(para)
            if not text:
                continue

            claimed: list[tuple[int, int]] = []

            # 1) Structural regex extraction (with centralized cleaning)
            for m in PHONE_RE.finditer(text):
                raw_val = m.group(0)
                value = clean_entity_surface(raw_val, "PHONE")
                if not value:
                    continue
                digits = re.sub(r"\D", "", value)
                # 10–13 digits, or short internal extensions like 555-0100
                if 6 <= len(digits) <= 13 and not re.fullmatch(r"\d{4}[-.\s]\d{4}", value):
                    claimed.append((m.start(), m.end()))
                    entities.append({
                        "entity_type": "PHONE", "value": value, "snippet": text,
                        "page": page_no, "paragraph": para_no,
                        "extractor": "regex.phone", "confidence": 0.95,
                    })

            for m in ACCOUNT_RE.finditer(text):
                raw_val = next((g for g in m.groups() if g), None)
                if raw_val:
                    value = clean_entity_surface(raw_val, "BANK_ACCOUNT")
                    if not value:
                        continue
                    claimed.append((m.start(), m.end()))
                    entities.append({
                        "entity_type": "BANK_ACCOUNT", "value": value, "snippet": text,
                        "page": page_no, "paragraph": para_no,
                        "extractor": "regex.account", "confidence": 0.9,
                    })

            for m in VEHICLE_RE.finditer(text):
                raw_val = m.group(1)
                value = clean_entity_surface(raw_val, "VEHICLE")
                if not value:
                    continue
                claimed.append((m.start(), m.end()))
                entities.append({
                    "entity_type": "VEHICLE", "value": value, "snippet": text,
                    "page": page_no, "paragraph": para_no,
                    "extractor": "regex.vehicle", "confidence": 0.9,
                })

            # 2) spaCy NER for PERSON / ORG / LOCATION
            if nlp is not None:
                doc = nlp(text)

                def _claimed(s: int, e: int) -> bool:
                    return any(not (e <= cs or s >= ce) for cs, ce in claimed)

                for ent in doc.ents:
                    label = NER_LABEL_MAP.get(ent.label_)
                    if not label:
                        continue
                    raw_val = ent.text
                    value = clean_entity_surface(raw_val, label)
                    if len(value) < 2 or _claimed(ent.start_char, ent.end_char):
                        continue

                    # ── Contextual PERSON vs LOCATION disambiguation ──────
                    # Inspect sentence prefix (up to 80 chars before entity) for spatial cues
                    sentence_prefix = text[max(0, ent.start_char - 80):ent.start_char]
                    # Ensure trailing space for regex \s+$ matching
                    refined = refine_entity_type(value, label, sentence_prefix + " ")
                    if refined != label:
                        # Re-clean with correct type's rules
                        value = clean_entity_surface(value, refined)
                        label = refined
                        if len(value) < 2:
                            continue

                    # ── Toponymic suffix/prefix override (Indian gazetteer fallback) ─
                    topo = apply_toponymic_rules(value, label)
                    if topo != label:
                        value = clean_entity_surface(value, topo)
                        label = topo
                        if len(value) < 2:
                            continue

                    # ── Header / form-label noise filters ─────────────────
                    # 1) All-caps headers like "RECORDED & ALIBI CORROBORATION"
                    if value.isupper() and len(value.split()) > 1:
                        continue
                    # 2) Strip label collocations first to salvage names like "Geetha Prabhakar Subject"
                    stripped = _strip_label_collocations(value, label)
                    if stripped != value:
                        if not stripped or len(stripped) < 2:
                            continue
                        # Re-check all-caps after stripping
                        if stripped.isupper() and len(stripped.split()) > 1:
                            continue
                        value = stripped
                    # 3) Block pure header labels and leaked form fields
                    if HEADER_LABEL_BLOCKLIST.search(value):
                        continue
                    if label == "ORG" and ORG_BLOCKLIST.search(value):
                        continue

                    # ── Conjoined span splitting (comma/and/&): "Rani, Anju" -> "Rani" + "Anju" ──
                    if label == "PERSON" and CONJOINED_SPLIT_RE.search(value):
                        # Only split if comma/& or standalone "and" present
                        if "," in value or "&" in value or re.search(r"\band\b", value, re.I):
                            parts = CONJOINED_SPLIT_RE.split(value)
                            emitted = False
                            for part in parts:
                                part = part.strip()
                                if not part:
                                    continue
                                part_val = clean_entity_surface(part, label)
                                part_val = _strip_label_collocations(part_val, label)
                                if len(part_val) < 2:
                                    continue
                                if part_val.isupper() and len(part_val.split()) > 1:
                                    continue
                                if HEADER_LABEL_BLOCKLIST.search(part_val):
                                    continue
                                if label == "ORG" and ORG_BLOCKLIST.search(part_val):
                                    continue
                                # Each split part is a separate candidate
                                conf_part = 0.85 if label == "PERSON" else 0.75
                                entities.append({
                                    "entity_type": label, "value": part_val,
                                    "snippet": text, "page": page_no, "paragraph": para_no,
                                    "extractor": "spacy.ner", "confidence": conf_part,
                                })
                                emitted = True
                            if emitted:
                                continue
                            # If no part survived, fall through to treat as single (will be discarded later)
                            continue

                    if label in {"PERSON", "ORG"}:
                        # Legacy report-style designators not covered by TITLE_PREFIX_RE
                        # (e.g., subject/informant) — keep for backward compat
                        value = re.sub(
                            r"^(subject|informant)\s+",
                            "", value, flags=re.I,
                        )
                        value = clean_entity_surface(value, label)
                        value = _strip_label_collocations(value, label)
                        # NER spans sometimes swallow a connector plus the next
                        # entity ("Maya Iyer to Hyderabad"). Keep the portion
                        # before the connector as this entity, and re-run NER on
                        # the discarded tail so the trailing entity (often a
                        # location) is still captured. ("of" is preserved.)
                        parts = re.split(
                            r"\s+(?:to|with|from|at)\s+", value, flags=re.I, maxsplit=1
                        )
                        value = clean_entity_surface(parts[0].strip(), label)
                        value = _strip_label_collocations(value, label)
                        if len(parts) > 1:
                            tail = clean_entity_surface(parts[1].strip(), "LOCATION")
                            tail = _strip_label_collocations(tail, "LOCATION")
                            if tail:
                                # Header check for tail
                                if not (tail.isupper() and len(tail.split()) > 1) and not HEADER_LABEL_BLOCKLIST.search(tail):
                                    tail_ents = nlp(tail).ents if nlp is not None else []
                                    if tail_ents:
                                        for tail_ent in tail_ents:
                                            tail_label = NER_LABEL_MAP.get(tail_ent.label_)
                                            tail_raw = tail_ent.text
                                            tail_value = clean_entity_surface(tail_raw, tail_label or "LOCATION")
                                            tail_value = _strip_label_collocations(tail_value, tail_label or "LOCATION")
                                            # Contextual refinement for tail as well
                                            tail_prefix = tail[max(0, tail_ent.start_char - 40):tail_ent.start_char] if hasattr(tail_ent, 'start_char') else ""
                                            refined_tail = refine_entity_type(tail_value, tail_label or "LOCATION", tail_prefix + " ")
                                            if refined_tail != (tail_label or "LOCATION"):
                                                tail_value = clean_entity_surface(tail_value, refined_tail)
                                                tail_label = refined_tail
                                            # Toponymic for tail
                                            topo_tail = apply_toponymic_rules(tail_value, tail_label or "LOCATION")
                                            if topo_tail != (tail_label or "LOCATION"):
                                                tail_value = clean_entity_surface(tail_value, topo_tail)
                                                tail_label = topo_tail
                                            if tail_value.isupper() and len(tail_value.split()) > 1:
                                                continue
                                            if HEADER_LABEL_BLOCKLIST.search(tail_value):
                                                continue
                                            if tail_label and len(tail_value) >= 2:
                                                entities.append({
                                                    "entity_type": tail_label, "value": tail_value,
                                                    "snippet": text, "page": page_no, "paragraph": para_no,
                                                    "extractor": "spacy.ner", "confidence": 0.7,
                                                })
                                    elif tail and tail[0].isupper() and len(tail.split()) <= 3:
                                        # Deterministic fallback: a title-case tail after a
                                        # PERSON+connector is usually a place ("…to Hyderabad")
                                        # that the small NER model misses on bare tokens.
                                        if not HEADER_LABEL_BLOCKLIST.search(tail):
                                            entities.append({
                                                "entity_type": "LOCATION", "value": tail,
                                                "snippet": text, "page": page_no, "paragraph": para_no,
                                                "extractor": "spacy.ner.tail", "confidence": 0.55,
                                            })
                        if len(value) < 2:
                            continue
                    else:
                        # For LOCATION etc., already cleaned and header-filtered, but ensure
                        value = _strip_label_collocations(value, label)
                        if value.isupper() and len(value.split()) > 1:
                            continue
                        if HEADER_LABEL_BLOCKLIST.search(value):
                            continue
                        value = clean_entity_surface(value, label)
                        if len(value) < 2:
                            continue
                    conf = 0.85 if label == "PERSON" else 0.75
                    entities.append({
                        "entity_type": label, "value": value, "snippet": text,
                        "page": page_no, "paragraph": para_no,
                        "extractor": "spacy.ner", "confidence": conf,
                    })

    # ── Procedural role assignment (explicit only, provenance-preserving) ──
    # Group PERSON entities by paragraph and scan that paragraph's text for explicit role cues.
    # Each role is tied to the same page/paragraph/sentence as the person mention.
    from collections import defaultdict as _defaultdict
    by_para_persons: dict[tuple[int, int], list[dict]] = _defaultdict(list)
    for _e in entities:
        if _e["entity_type"] == "PERSON":
            by_para_persons[(_e["page"], _e["paragraph"])].append(_e)
    text_by_para: dict[tuple[int, int], str] = {}
    for _pg in pages:
        _pnum = _pg.get("page", 0)
        for _idx, _para in enumerate(_pg.get("paragraphs", []), start=1):
            text_by_para[(_pnum, _idx)] = _para
    for _key, _persons in by_para_persons.items():
        _para_text = text_by_para.get(_key, "")
        if not _para_text:
            continue
        _role_map = extract_procedural_roles(_para_text, _persons)
        for _p in _persons:
            _role = _role_map.get(_p["value"].lower())
            if _role:
                _p["procedural_role"] = _role
            elif "procedural_role" not in _p:
                _p["procedural_role"] = ""
    # Ensure all entities have procedural_role field (empty for non-PERSON)
    for _e in entities:
        if "procedural_role" not in _e:
            _e["procedural_role"] = "" if _e["entity_type"] == "PERSON" else ""

    # Deduplicate identical (type, value, page, paragraph) rows — keep first role if duplicate
    seen = set()
    unique = []
    for e in entities:
        key = (e["entity_type"], e["value"].lower(), e["page"], e["paragraph"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
        else:
            # If duplicate was discarded but had a role, propagate role to the kept entry
            for u in unique:
                if (u["entity_type"], u["value"].lower(), u["page"], u["paragraph"]) == key and e.get("procedural_role"):
                    if not u.get("procedural_role"):
                        u["procedural_role"] = e["procedural_role"]
                    break
    return unique
