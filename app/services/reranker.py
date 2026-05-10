from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Iterable

from app.models.catalog import CatalogItem

TOKEN_RE = re.compile(r"[a-zA-Z0-9+.#()-]+")
STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "with", "by",
    "i", "we", "you", "me", "my", "our", "is", "are", "am", "be", "need", "needs",
    "want", "wanted", "looking", "look", "assessment", "test", "tests", "tool",
    "role", "job", "hire", "hiring", "candidate", "candidates", "please", "show",
    "give", "find", "best", "right", "fit", "fitment", "screening", "quickly",
    "daily", "day", "days",
}

QUICK_HINTS = {"quick", "quickly", "fast", "short", "brief", "screen", "screening"}
OFFICE_HINTS = {
    "admin", "administrative", "assistant", "assistants", "office", "clerical",
    "back office", "support", "operations", "coordinator", "secretary", "reception",
}
EXCEL_HINTS = {"excel", "spreadsheet", "sheet", "workbook"}
WORD_HINTS = {"word", "document", "docs", "doc", "processing"}
PERSONALITY_HINTS = {
    "personality", "behavior", "behaviour", "fit", "fitment", "culture",
    "stakeholder", "communication", "teamwork", "collaboration", "leadership",
    "people", "interaction",
}
SIMULATION_HINTS = {"simulation", "simulate", "practical", "hands-on", "end-to-end"}

@dataclass
class RankedCandidate:
    item: CatalogItem
    score: float
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    debug: dict = field(default_factory=dict)

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]

def _content_tokens(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in STOPWORDS and len(t) > 1}

def _char_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def _token_overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def _extract_duration_hint(query: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*(?:min|mins|minute|minutes)\b", query.lower())
    return int(m.group(1)) if m else None

def _parse_duration_text(duration: str) -> int | None:
    m = re.search(r"(\d{1,3})", duration or "")
    return int(m.group(1)) if m else None

def _field_text(item: CatalogItem) -> str:
    return " ".join([
        item.name or "",
        item.description or "",
        " ".join(item.job_levels or []),
        " ".join(item.languages or []),
        item.duration or "",
        " ".join(item.keys or []),
    ]).strip()

def _has_any(query: str, phrases: set[str]) -> bool:
    q = query.lower()
    return any(p in q for p in phrases)

def _extract_signals(query: str) -> dict:
    q = query.lower()
    q_tokens = set(_tokens(q))
    return {
        "quick": _has_any(q, QUICK_HINTS),
        "office": _has_any(q, OFFICE_HINTS),
        "excel": _has_any(q, EXCEL_HINTS),
        "word": _has_any(q, WORD_HINTS),
        "personality": _has_any(q, PERSONALITY_HINTS),
        "simulation": _has_any(q, SIMULATION_HINTS),
        "duration_hint": _extract_duration_hint(q),
        "query_tokens": q_tokens,
    }

def _item_family(item: CatalogItem) -> str:
    text = _normalize(" ".join([
        item.name or "",
        item.description or "",
        " ".join(item.keys or []),
    ]))
    if any(x in text for x in ["excel", "spreadsheet"]):
        return "excel"
    if any(x in text for x in ["word", "document", "word processing"]):
        return "word"
    if any(x in text for x in ["personality", "opq", "behaviour", "behavior"]):
        return "personality"
    if any(x in text for x in ["basic computer literacy", "computer literacy", "office"]):
        return "office_basics"
    if any(x in text for x in ["simulation", "work sample", "practical", "hands-on"]):
        return "simulation"
    return "other"

def rerank(query: str, candidates: list[dict], top_k: int = 10) -> list[RankedCandidate]:
    """
    candidates: list of dicts like:
      {
        "item": CatalogItem,
        "semantic_score": float,
        "lexical_score": float
      }
    """
    q = _normalize(query)
    q_tokens = _content_tokens(q)
    q_all_tokens = set(_tokens(q))
    signals = _extract_signals(query)
    q_duration = signals["duration_hint"]

    ranked: list[RankedCandidate] = []

    for cand in candidates:
        item: CatalogItem = cand["item"]
        semantic = float(cand.get("semantic_score", 0.0))
        lexical = float(cand.get("lexical_score", 0.0))

        name = _normalize(item.name or "")
        doc = _normalize(_field_text(item))
        name_tokens = _content_tokens(name)
        doc_tokens = _content_tokens(doc)
        family = _item_family(item)

        score = 0.0
        debug = {}

        # Base retrieval scores
        score += 0.50 * semantic
        score += 0.08 * lexical
        debug["semantic"] = semantic
        debug["lexical"] = lexical

        # Strong title matching
        title_exact = 1.0 if item.name and item.name.lower() in q else 0.0
        title_overlap = _token_overlap(q_tokens, name_tokens)
        title_sim = _char_similarity(q, name)

        score += 0.20 * title_exact
        score += 0.14 * title_overlap
        score += 0.08 * title_sim

        debug["title_exact"] = title_exact
        debug["title_overlap"] = title_overlap
        debug["title_sim"] = title_sim

        # Field-level match
        key_hit = _token_overlap(q_all_tokens, {x.lower() for x in (item.keys or [])})
        lang_hit = _token_overlap(q_all_tokens, {x.lower() for x in (item.languages or [])})
        job_level_hit = _token_overlap(q_all_tokens, {x.lower() for x in (item.job_levels or [])})
        desc_sim = _char_similarity(q, doc)

        score += 0.14 * key_hit
        score += 0.04 * lang_hit
        score += 0.08 * job_level_hit
        score += 0.04 * desc_sim

        debug["key_hit"] = key_hit
        debug["lang_hit"] = lang_hit
        debug["job_level_hit"] = job_level_hit
        debug["desc_sim"] = desc_sim

        # Duration preference: shorter gets favored for "quick" requests
        item_duration = _parse_duration_text(item.duration)
        duration_bonus = 0.0

        if q_duration and item_duration:
            diff = abs(q_duration - item_duration)
            duration_bonus = max(0.0, 1.0 - (diff / max(q_duration, item_duration, 1)))
            score += 0.08 * duration_bonus

        if signals["quick"] and item_duration:
            if item_duration <= 10:
                score += 0.22
            elif item_duration <= 15:
                score += 0.12
            elif item_duration >= 20:
                score -= 0.18

        debug["duration_bonus"] = duration_bonus

        # Role-specific boosts for admin/office requests
        if signals["office"]:
            if family in {"excel", "word", "office_basics"}:
                score += 0.28
            if any(x in doc for x in ["administrative", "office", "clerical", "support"]):
                score += 0.12

        # Software-specific boosts
        if signals["excel"]:
            if family == "excel":
                score += 0.35
            if "spreadsheet" in doc or "excel" in doc:
                score += 0.10

        if signals["word"]:
            if family == "word":
                score += 0.35
            if "word processing" in doc or "document" in doc:
                score += 0.10

        # Personality / behavioural fit for screening requests
        if signals["personality"] or any(x in q_all_tokens for x in {"screen", "screening", "hire", "hiring"}):
            if family == "personality":
                score += 0.30
            if any(x in doc for x in ["personality", "behavior", "behaviour", "work style"]):
                score += 0.10

        # Prefer knowledge tools over simulations when the user says "quick"
        if signals["quick"]:
            if family == "simulation":
                score -= 0.22
            if any(x in doc for x in ["knowledge", "skills", "mcq", "multiple choice"]):
                score += 0.10

        # If user explicitly asks for practical/simulation, flip that preference
        if signals["simulation"]:
            if family == "simulation":
                score += 0.28
            if any(x in doc for x in ["practical", "simulation", "work sample"]):
                score += 0.10

        # General behavioral words
        behavioral_words = {
            "stakeholder", "communication", "collaboration", "teamwork",
            "leadership", "personality", "client", "manager", "people", "interaction"
        }
        if signals["personality"]:
            behavior_hits = sum(1 for word in behavioral_words if word in doc)
            score += 0.03 * behavior_hits

        # Gentle promotion for exact admin-assistant style items
        if any(x in q_all_tokens for x in {"assistant", "assistants", "admin", "administrative"}):
            if family in {"office_basics", "word", "excel"}:
                score += 0.10

        ranked.append(
            RankedCandidate(
                item=item,
                score=score,
                semantic_score=semantic,
                lexical_score=lexical,
                debug=debug,
            )
        )

    ranked.sort(key=lambda x: x.score, reverse=True)

    # Diversity pass: keep useful variety, but don't let near-duplicates dominate.
    final: list[RankedCandidate] = []
    seen_names = set()
    seen_family = {}

    for r in ranked:
        name_key = (r.item.name or "").lower().strip()
        if name_key in seen_names:
            continue

        family = _item_family(r.item)
        penalty = 0.0

        # Light penalty only when a family is over-represented.
        family_count = seen_family.get(family, 0)
        if family_count >= 1:
            penalty += 0.06 * family_count

        # For quick admin screens, allow one strong Excel, one strong Word, and optionally one personality.
        if signals["office"] and signals["quick"]:
            if family in {"excel", "word", "personality"}:
                penalty -= 0.02  # slight encouragement

        r.score -= penalty
        final.append(r)
        seen_names.add(name_key)
        seen_family[family] = family_count + 1

    final.sort(key=lambda x: x.score, reverse=True)
    return final[:top_k]