import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.catalog_loader import (
    load_catalog,
)

from app.services.vector_store import (
    ChromaVectorStore,
)

catalog = load_catalog()

store = ChromaVectorStore()

store.add_documents(catalog)

print("Indexes built.")
