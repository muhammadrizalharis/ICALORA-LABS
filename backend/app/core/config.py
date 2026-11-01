"""Konfigurasi aplikasi ICALORA-LABS (dibaca dari environment / .env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Aplikasi
    app_name: str = "ICALORA-LABS API"
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    cors_origins: str = Field(default="http://localhost:3000")

    # PostgreSQL (infra lokal: 127.0.0.1:54432)
    postgres_host: str = Field(default="127.0.0.1")
    postgres_port: int = Field(default=54432)
    postgres_user: str = Field(default="icalora")
    postgres_password: str = Field(default="")
    postgres_db: str = Field(default="icalora")

    # Redis (infra lokal: 127.0.0.1:54379)
    redis_host: str = Field(default="127.0.0.1")
    redis_port: int = Field(default=54379)
    redis_password: str = Field(default="")

    # SeaweedFS S3 (infra lokal: 127.0.0.1:54333)
    s3_endpoint: str = Field(default="http://127.0.0.1:54333")
    s3_access_key: str = Field(default="icalora")
    s3_secret_key: str = Field(default="")
    s3_region: str = Field(default="us-east-1")
    s3_bucket: str = Field(default="icalora")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
