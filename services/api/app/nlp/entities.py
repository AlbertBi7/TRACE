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

# Noise filters for NER hits
ORG_BLOCKLIST = re.compile(
    r"\b(bank|police|court|department|ministry|bureau|team|case|unit|report)\b", re.I
)


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

            # 1) Structural regex extraction
            for m in PHONE_RE.finditer(text):
                value = _clean(m.group(0))
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
                value = next((g for g in m.groups() if g), None)
                if value:
                    claimed.append((m.start(), m.end()))
                    entities.append({
                        "entity_type": "BANK_ACCOUNT", "value": value, "snippet": text,
                        "page": page_no, "paragraph": para_no,
                        "extractor": "regex.account", "confidence": 0.9,
                    })

            for m in VEHICLE_RE.finditer(text):
                value = _clean(m.group(1))
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
                    value = _clean(ent.text)
                    if len(value) < 2 or _claimed(ent.start_char, ent.end_char):
                        continue
                    if label == "ORG" and ORG_BLOCKLIST.search(value):
                        continue
                    if label in {"PERSON", "ORG"}:
                        # Strip report-style designators so "Subject Rohan Mehra"
                        # resolves to the same person as "Rohan Mehra".
                        value = re.sub(
                            r"^(subject|suspect|witness|victim|informant|mr|mrs|ms|dr)\s+",
                            "", value, flags=re.I,
                        )
                        # NER spans sometimes swallow a connector plus the next
                        # entity ("Maya Iyer to Hyderabad"). Keep the portion
                        # before the connector as this entity, and re-run NER on
                        # the discarded tail so the trailing entity (often a
                        # location) is still captured. ("of" is preserved.)
                        parts = re.split(
                            r"\s+(?:to|with|from|at)\s+", value, flags=re.I, maxsplit=1
                        )
                        value = parts[0].strip()
                        if len(parts) > 1:
                            tail = parts[1].strip()
                            tail_ents = nlp(tail).ents if nlp is not None else []
                            if tail_ents:
                                for tail_ent in tail_ents:
                                    tail_label = NER_LABEL_MAP.get(tail_ent.label_)
                                    tail_value = _clean(tail_ent.text)
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
                                entities.append({
                                    "entity_type": "LOCATION", "value": _clean(tail),
                                    "snippet": text, "page": page_no, "paragraph": para_no,
                                    "extractor": "spacy.ner.tail", "confidence": 0.55,
                                })
                        if len(value) < 2:
                            continue
                    conf = 0.85 if label == "PERSON" else 0.75
                    entities.append({
                        "entity_type": label, "value": value, "snippet": text,
                        "page": page_no, "paragraph": para_no,
                        "extractor": "spacy.ner", "confidence": conf,
                    })

    # Deduplicate identical (type, value, page, paragraph) rows
    seen = set()
    unique = []
    for e in entities:
        key = (e["entity_type"], e["value"].lower(), e["page"], e["paragraph"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique
