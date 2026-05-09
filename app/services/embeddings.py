from sentence_transformers import SentenceTransformer
from app.core.config import settings

model = SentenceTransformer(settings.EMBED_MODEL)

def embed_text(texts: list[str]):
    return model.encode(
        texts,
        normalize_embeddings=True
    ).tolist()