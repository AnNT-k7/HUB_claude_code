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
        "postgresql+psycopg2://postgres:postgres@localhost:5432/"
        "digital_expert_agents"
    )
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    minio_url: str = "http://localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket_name: str = "case-documents"
    minio_secure: bool = False

    openai_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

