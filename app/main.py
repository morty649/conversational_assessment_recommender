from fastapi import FastAPI

from app.api.routes import (
    router,
    agent_instance,
)

from app.services.catalog_loader import (
    load_catalog,
)

from app.services.vector_store import (
    ChromaVectorStore,
)

from app.services.bm25_store import (
    BM25Store,
)

from app.services.retrieval import (
    HybridRetriever,
)

from app.services.agent import (
    SHLAgent,
)

app = FastAPI()

catalog = load_catalog()

vector_store = ChromaVectorStore()

vector_store.add_documents(catalog)

bm25_store = BM25Store(catalog)

retriever = HybridRetriever(
    vector_store,
    bm25_store,
)

from app.api import routes

routes.agent_instance = SHLAgent(
    retriever
)

app.include_router(router)