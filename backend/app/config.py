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
    # The demo must run without Docker. PostgreSQL remains supported by setting
    # DATABASE_URL, while the local default is a persistent SQLite database.
    database_url: str = "sqlite:///./data/income_verification.db"
    document_storage_root: str = "./data/case_documents"
    max_document_size_bytes: int = 25 * 1024 * 1024
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    minio_url: str = "http://localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket_name: str = "case-documents"
    minio_secure: bool = False

    openai_api_key: str = ""
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_request_timeout_seconds: float = 60.0
    fpt_api_key: str = ""
    fpt_base_url: str = "https://mkp-api.fptcloud.com"
    fpt_request_timeout_seconds: float = 60.0
    llm_provider: str = "fpt"
    llm_model: str = ""
    llm_max_attempts: int = 2
    llm_temperature: float = 0.1
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
