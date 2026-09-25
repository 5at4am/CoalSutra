from pydantic import model_validator
from pydantic_settings import BaseSettings


def _blank_env_values_fall_back_to_defaults(cls, values):
    for field_name in cls.model_fields:
        if values.get(field_name) in ("", None):
            values.pop(field_name, None)
    return values


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    _blank_env_fallback = model_validator(mode="before")(
        classmethod(_blank_env_values_fall_back_to_defaults)
    )

    DATABASE_URL: str = "postgresql+psycopg2://cmpdi:cmpdi@localhost:5432/cmpdi"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TIMEOUT: float = 60.0
    # Listed USD-per-1M-token prices used by the Evaluate dashboard to estimate
    # spend from recorded usage. Defaults match gpt-4o-mini; override to match
    # the actual provider/model (e.g. Groq or a self-hosted gateway).
    LLM_PRICE_PER_1M_INPUT_USD: float = 0.15
    LLM_PRICE_PER_1M_OUTPUT_USD: float = 0.60
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

    # Prototype authentication (HMAC-signed bearer tokens, no external deps).
    # AUTH_ENABLED=false keeps the API fully open (used by the offline test
    # suite; also handy for local dev). With AUTH_ENABLED=true every route
    # except /auth/login and /health requires `Authorization: Bearer <token>`.
    AUTH_ENABLED: bool = True
    # Signing secret for tokens. Leave empty to use the bundled dev default —
    # set a real value in production.
    AUTH_SECRET: str = ""
    # Demo users "username:password". Prototype only — plaintext on purpose so
    # the POC can ship demo credentials; a real deployment needs a users table
    # with hashed passwords.
    DEMO_USERS: dict[str, str] = {
        "admin": "admin123",
        "analyst": "analyst123",
        "reviewer": "reviewer123",
    }
    AUTH_TOKEN_TTL_SECONDS: int = 60 * 60 * 24 * 7


settings = Settings()