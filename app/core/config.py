from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    CHROMA_PATH: str = "data/chroma"
    CATALOG_PATH: str = "data/shl_catalog.json"

    EMBED_MODEL: str = "sentence-transformers/all-mpnet-base-v2"
    EMBED_LOCAL_FILES_ONLY: bool = False

    TOP_K_RETRIEVAL: int = 20
    TOP_K_FINAL: int = 10

    class Config:
        env_file = ".env"

settings = Settings()
