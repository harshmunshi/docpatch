"""MockModelClient for tests. Never makes real API calls."""

from __future__ import annotations

from collections.abc import Callable

from docpatch.models.base import ModelResponse


class MockModelClient:
    """Returns a fixed string or calls a callback. Used in all non-live tests."""

    def __init__(self, response: str | Callable[[str], str] = "") -> None:
        self._response = response

    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        text = self._response(prompt) if callable(self._response) else self._response
        return ModelResponse(
            text=text,
            tokens_in=len(prompt.split()),
            tokens_out=len(text.split()),
            model_id="mock",
        )
