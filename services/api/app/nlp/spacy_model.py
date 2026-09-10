"""
TRACE — spaCy model singleton
Lazy-loads the configured model once; degrades to None if unavailable so the
regex-only path keeps working without spaCy.
"""

import logging
import threading

from app.config import settings

logger = logging.getLogger("trace.nlp")

_nlp = None
_lock = threading.Lock()


def get_nlp():
    """Return the loaded spaCy model, or None if it cannot be loaded."""
    global _nlp
    if _nlp is not None:
        return _nlp
    with _lock:
        if _nlp is None:
            try:
                import spacy

                _nlp = spacy.load(settings.spacy_model)
                logger.info(f"spaCy model '{settings.spacy_model}' loaded")
            except Exception as e:
                logger.warning(f"spaCy unavailable ({e}) — using regex-only extraction")
                return None
    return _nlp
