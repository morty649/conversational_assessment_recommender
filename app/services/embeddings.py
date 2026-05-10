from sentence_transformers import SentenceTransformer
from app.core.config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(
            settings.EMBED_MODEL,
            local_files_only=settings.EMBED_LOCAL_FILES_ONLY,
        )
    return _model

def embed_text(texts: list[str]):
    return _get_model().encode(
        texts,
        normalize_embeddings=True
    ).tolist()
