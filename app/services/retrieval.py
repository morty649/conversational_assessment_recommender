from __future__ import annotations

from typing import Any

from app.core.config import settings


class HybridRetriever:
    def __init__(self, vector_store, bm25_store):
        self.vector_store = vector_store
        self.bm25_store = bm25_store

    def retrieve(self, query: str, k: int = 20) -> list[dict]:
        semantic = {"metadatas": [[]], "distances": [[]]}
        if settings.ENABLE_SEMANTIC_RETRIEVAL:
            semantic = self.vector_store.semantic_search(query, k=k)

        lexical = self.bm25_store.search(query, k=k)

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

        return [v for v in merged.values() if v["item"] is not None]
