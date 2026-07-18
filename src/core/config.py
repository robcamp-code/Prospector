"""Pydantic Settings configuration replacing load_dotenv."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://postgres:postgres@localhost:5432/prospector"
    openai_api_key: SecretStr = SecretStr("")
    model: str = "gpt-4o"
    debug: bool = False

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        ).replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
