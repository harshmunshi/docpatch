"""Global settings, loaded from DOCPATCH_* env vars. No singletons."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCPATCH_", env_file=".env", extra="ignore")

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
