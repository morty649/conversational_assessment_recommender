from __future__ import annotations

from typing import Any
from time import perf_counter

from app.core.config import settings


class HybridRetriever:
    def __init__(self, vector_store, bm25_store):
        self.vector_store = vector_store
        self.bm25_store = bm25_store
        self.last_timings: dict[str, float] = {}

    def retrieve(self, query: str, k: int = 20) -> list[dict]:
        timings = {}
        retrieval_started = perf_counter()
        semantic = {"metadatas": [[]], "distances": [[]]}

        if settings.ENABLE_SEMANTIC_RETRIEVAL:
            stage_started = perf_counter()
            semantic, semantic_timings = self.vector_store.semantic_search(
                query,
                k=k,
            )
            timings["semantic_search"] = perf_counter() - stage_started
            timings["embedding"] = semantic_timings.get("embedding", 0.0)
            timings["chroma_query"] = semantic_timings.get("chroma_query", 0.0)

        stage_started = perf_counter()
        lexical = self.bm25_store.search(query, k=k)
        timings["bm25"] = perf_counter() - stage_started

        stage_started = perf_counter()
        merged: dict[str, dict[str, Any]] = {}

        sem_metas = semantic.get("metadatas", [[]])[0]
        sem_dists = semantic.get("distances", [[]])[0]

        for meta, dist in zip(sem_metas, sem_dists):
            name = (meta.get("name") or "").strip()
            if not name:
                continue
            item = self.bm25_store.by_name.get(name.lower().strip())
            if item is None:
                continue

            score = max(0.0, 1.0 - dist)
            merged[name.lower().strip()] = {
                "item": item,
                "semantic_score": score,
                "lexical_score": 0.0,
            }

        for item, score in lexical:
            key = item.name.lower().strip()
            if key not in merged:
                merged[key] = {
                    "item": item,
                    "semantic_score": 0.0,
                    "lexical_score": float(score),
                }
            else:
                merged[key]["lexical_score"] = float(score)

        timings["merge"] = perf_counter() - stage_started
        timings["retrieval_total"] = perf_counter() - retrieval_started
        self.last_timings = timings

        return [v for v in merged.values() if v["item"] is not None]
