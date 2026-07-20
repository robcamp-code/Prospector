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
    # LLM model (langchain init_chat_model format: "provider:model-id").
    # Options, cheapest → most capable — bump up if output quality is low:
    #   "anthropic:claude-haiku-4-5"   # fastest / cheapest, simple tasks
    #   "anthropic:claude-sonnet-5"    # balanced speed & intelligence
    #   "anthropic:claude-opus-4-8"    # strong default, best for agentic work
    #   "anthropic:claude-fable-5"     # most capable, premium pricing
    model: str = "anthropic:claude-opus-4-8"
    debug: bool = False

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        ).replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
