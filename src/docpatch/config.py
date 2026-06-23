"""Global settings, loaded from DOCPATCH_* env vars and .env. No singletons."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCPATCH_", env_file=".env", extra="ignore")

    # Provider API keys — read standard names directly (bypass DOCPATCH_ prefix)
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    # Locator
    semantic_locator_threshold: float = 0.6
    max_locate_candidates: int = 5

    # Patcher
    max_retry: int = 3
    max_tokens: int = 4096

    # Storage
    sidecar_dir_name: str = ".dpx"

    # Logging
    log_level: str = "INFO"
    log_json: bool = False
