from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    DATABASE_URL: str = "postgresql+psycopg2://cmpdi:cmpdi@localhost:5432/cmpdi"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TIMEOUT: float = 60.0
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    # "api"  → request embeddings from LLM_BASE_URL/embeddings (OpenAI-compatible)
    # "hash" → deterministic local hashing (Groq/chat-only providers, offline demo)
    EMBEDDING_PROVIDER: str = "api"
    OCR_PROVIDER: str = "tesseract"
    # Hugging Face Inference API OCR (image-to-text model on the hosted endpoint).
    HUGGINGFACE_API_KEY: str = ""
    OCR_HF_MODEL: str = "microsoft/trocr-base-printed"

    PROJECT_NAME: str = "CoalSutra — CMPDI Reporting Assistant"
    API_V1_PREFIX: str = "/api/v1"

    UPLOAD_DIR: str = "./uploads"


settings = Settings()