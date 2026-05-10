import chromadb
import hashlib
import re
from time import perf_counter

from app.services.embeddings import embed_text
from app.core.config import settings


def _collection_name() -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", settings.EMBED_MODEL).strip("_")
    digest = hashlib.sha1(settings.EMBED_MODEL.encode()).hexdigest()[:8]
    return f"shl_catalog_{slug[:32]}_{digest}"


class ChromaVectorStore:

    def __init__(self):

        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PATH
        )

        self.collection = self.client.get_or_create_collection(
            name=_collection_name()
        )

    def add_documents(self, items):
        if self.collection.count() >= len(items):
            return

        docs = []
        ids = []
        metas = []

        for item in items:

            docs.append(item.searchable_text())

            ids.append(item.entity_id)

            metas.append({
                "name": item.name,
                "url": item.link,
                "keys": ", ".join(item.keys),
                "job_levels": ", ".join(item.job_levels),
            })

        embeddings = embed_text(docs)

        self.collection.upsert(
            ids=ids,
            documents=docs,
            embeddings=embeddings,
            metadatas=metas,
        )

    def semantic_search(self, query: str, k: int = 10):
        timings = {}

        stage_started = perf_counter()
        query_embedding = embed_text([query])[0]
        timings["embedding"] = perf_counter() - stage_started

        stage_started = perf_counter()
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
        )
        timings["chroma_query"] = perf_counter() - stage_started

        return result, timings
