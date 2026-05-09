import chromadb

from app.services.embeddings import embed_text
from app.core.config import settings

class ChromaVectorStore:

    def __init__(self):

        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PATH
        )

        self.collection = self.client.get_or_create_collection(
            name="shl_catalog"
        )

    def add_documents(self, items):

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

        result = self.collection.query(
            query_texts=[query],
            n_results=k,
        )

        return result