import logging
from time import perf_counter

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
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

startup_started = perf_counter()
app = FastAPI()

stage_started = perf_counter()
catalog = load_catalog()
catalog_load_ms = (perf_counter() - stage_started) * 1000

stage_started = perf_counter()
vector_store = ChromaVectorStore()
vector_store_init_ms = (perf_counter() - stage_started) * 1000

stage_started = perf_counter()
vector_store.add_documents(catalog)
vector_index_ms = (perf_counter() - stage_started) * 1000

stage_started = perf_counter()
bm25_store = BM25Store(catalog)
bm25_init_ms = (perf_counter() - stage_started) * 1000

retriever = HybridRetriever(
    vector_store,
    bm25_store,
)

from app.api import routes

routes.agent_instance = SHLAgent(
    retriever
)

app.include_router(router)

logger.info(
    "startup_timing catalog_items=%s catalog_load_ms=%.1f vector_store_init_ms=%.1f "
    "vector_index_ms=%.1f bm25_init_ms=%.1f total_startup_ms=%.1f chroma_path=%s",
    len(catalog),
    catalog_load_ms,
    vector_store_init_ms,
    vector_index_ms,
    bm25_init_ms,
    (perf_counter() - startup_started) * 1000,
    settings.CHROMA_PATH,
)
