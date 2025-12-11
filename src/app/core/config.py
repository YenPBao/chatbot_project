from __future__ import annotations

from functools import lru_cache
from typing import Optional
from pathlib import Path

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH) if _ENV_PATH.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==== Model / Provider API keys ====
    openai_api_key: Optional[SecretStr] = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: Optional[SecretStr] = Field(default=None, alias="GOOGLE_API_KEY")

    # ==== Database ====
    database_url: Optional[str] = Field(default=None, alias="DB_URL")

    # ==== LangSmith ====
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_endpoint: Optional[str] = Field(default=None, alias="LANGSMITH_ENDPOINT")
    langsmith_api_key: Optional[SecretStr] = Field(
        default=None, alias="LANGSMITH_API_KEY"
    )
    langsmith_project: Optional[str] = Field(default=None, alias="LANGSMITH_PROJECT")

    # ==== App settings ====
    env: str = Field(default="local", alias="ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    # ==== App server ====
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    # ==== Redis ====
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")

    # ==== Elasticsearch ====
    elastic_url: Optional[str] = Field(default=None, alias="ELASTIC_URL")
    elastic_index: str = Field(default="docs", alias="ELASTIC_INDEX")

    # ==== JWT Auth ====
    jwt_secret: Optional[SecretStr] = Field(default=None, alias="JWT_SECRET")
    access_expire_seconds: int = Field(default=3600, alias="ACCESS_EXPIRE_SECONDS")
    refresh_expire_seconds: int = Field(
        default=7 * 24 * 3600, alias="REFRESH_EXPIRE_SECONDS"
    )
    jwt_alg: str = Field(default="HS256", alias="JWT_ALG")

    # ==== Derived / helpers ====
    @computed_field
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    @computed_field
    def is_local(self) -> bool:
        return self.env.lower() in {"dev", "local", "development"}

    def require_jwt_secret(self) -> str:
        if self.jwt_secret is None:
            raise RuntimeError(
                "JWT_SECRET is not set. Please configure it in your environment/.env."
            )
        return self.jwt_secret.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
