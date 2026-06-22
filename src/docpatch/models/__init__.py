"""LLM client abstraction. No provider is a hard dependency."""

from docpatch.models.base import ModelClient, ModelResponse

__all__ = ["ModelClient", "ModelResponse"]
