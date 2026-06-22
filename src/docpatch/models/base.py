"""ModelClient Protocol and ModelResponse. No provider imports here."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ModelResponse(BaseModel):
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model_id: str = ""


@runtime_checkable
class ModelClient(Protocol):
    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse: ...
