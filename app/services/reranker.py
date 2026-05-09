
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
    "give", "find", "best", "right", "fit", "fitment", "screening",
}

SENIORITY_HINTS = {
    "entry-level", "entry level", "graduate", "junior", "mid", "mid-level",
    "mid professional", "mid-professional", "senior", "manager", "director",
    "executive", "supervisor", "front line manager", "front-line manager",
    "general population",
}

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
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def _extract_duration_hint(query: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*(?:min|mins|minute|minutes)\b", query.lower())
    return int(m.group(1)) if m else None

def _extract_job_level_hints(query: str) -> set[str]:
    q = query.lower()
    return {hint for hint in SENIORITY_HINTS if hint in q}

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
    q_duration = _extract_duration_hint(q)
    q_levels = _extract_job_level_hints(q)

    ranked: list[RankedCandidate] = []

    for cand in candidates:
        item: CatalogItem = cand["item"]
        semantic = float(cand.get("semantic_score", 0.0))
        lexical = float(cand.get("lexical_score", 0.0))

        name = _normalize(item.name)
        doc = _normalize(_field_text(item))
        name_tokens = _content_tokens(name)
        doc_tokens = _content_tokens(doc)

        score = 0.0
        debug = {}

        score += 0.65 * semantic
        score += 0.10 * lexical
        debug["semantic"] = semantic
        debug["lexical"] = lexical

        title_exact = 1.0 if item.name and item.name.lower() in q else 0.0
        title_overlap = _token_overlap(q_tokens, name_tokens)
        title_sim = _char_similarity(q, name)

        score += 0.18 * title_overlap
        score += 0.12 * title_sim
        score += 0.20 * title_exact

        debug["title_overlap"] = title_overlap
        debug["title_sim"] = title_sim
        debug["title_exact"] = title_exact

        job_level_hit = _token_overlap(q_all_tokens, {x.lower() for x in (item.job_levels or [])})
        key_hit = _token_overlap(q_all_tokens, {x.lower() for x in (item.keys or [])})
        lang_hit = _token_overlap(q_all_tokens, {x.lower() for x in (item.languages or [])})

        score += 0.16 * job_level_hit
        score += 0.14 * key_hit
        score += 0.06 * lang_hit

        debug["job_level_hit"] = job_level_hit
        debug["key_hit"] = key_hit
        debug["lang_hit"] = lang_hit

        item_duration = _parse_duration_text(item.duration)
        duration_bonus = 0.0
        if q_duration and item_duration:
            diff = abs(q_duration - item_duration)
            duration_bonus = max(0.0, 1.0 - (diff / max(q_duration, item_duration, 1)))
            score += 0.08 * duration_bonus
        debug["duration_bonus"] = duration_bonus

        level_bonus = 0.0
        if q_levels and item.job_levels:
            item_levels = {x.lower().strip() for x in item.job_levels}
            if any(h in item_levels for h in q_levels):
                level_bonus = 1.0
                score += 0.14
        debug["level_bonus"] = level_bonus

        desc_sim = _char_similarity(q, doc)
        score += 0.05 * desc_sim
        debug["desc_sim"] = desc_sim

     

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

    seen = set()
    final: list[RankedCandidate] = []
    for r in ranked:
        key = r.item.name.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        final.append(r)
        if len(final) >= top_k:
            break

    return final