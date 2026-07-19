from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Digital Expert Agents API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5433/"
        "digital_expert_agents"
    )
    # Case-management persistence (multi-case API, uploaded documents, audit
    # log). SQLite by default so the whole MVP runs with zero external
    # services; point this at a Postgres DSN to move the same schema there.
    case_database_url: str = "sqlite:///./data/case_management.db"
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    minio_url: str = "http://localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket_name: str = "case-documents"
    minio_secure: bool = False

    # Chat/completions LLM provider — drives app/services/llm_provider.py.
    # "fpt" is the default because it's the key issued for this competition;
    # "mock" (no key required) is the deterministic fallback used in tests.
    llm_provider: str = "fpt"
    llm_model: str = "SaoLa3.1-medium"
    llm_request_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_request_timeout_seconds: float = 60.0
    fpt_api_key: str = ""
    fpt_base_url: str = "https://mkp-api.fptcloud.com"
    fpt_request_timeout_seconds: float = 60.0
    embedding_provider: str = "fpt"
    embedding_model: str = "Vietnamese_Embedding"
    embedding_dimensions: int = 512
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16
    embedding_trust_remote_code: bool = True
    embedding_cache_dir: str = ".cache/huggingface"


@lru_cache
def get_settings() -> Settings:
    return Settings()

