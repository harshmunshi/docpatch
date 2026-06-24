"""OpenAI model client. Requires `pip install docpatch[openai]`."""

from __future__ import annotations

from typing import Any

from docpatch.core.errors import ModelError
from docpatch.models.base import ModelResponse

_openai: Any
try:
    import openai as _openai
except ImportError:
    _openai = None


class OpenAIClient:
    """Thin wrapper around the OpenAI Chat Completions API."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
    ) -> None:
        if _openai is None:
            raise ModelError(
                ModelError.Kind.MISSING_EXTRA,
                "Install openai extra: pip install docpatch[openai]",
            )
        self._model = model
        self._client = _openai.OpenAI(api_key=api_key)

    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ModelError(ModelError.Kind.API_ERROR, str(exc)) from exc

        choice = resp.choices[0]
        finish = getattr(choice, "finish_reason", None)
        if finish == "content_filter":
            raise ModelError(ModelError.Kind.API_ERROR, "response blocked by content filter")
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            raise ModelError(ModelError.Kind.API_ERROR, f"model refused: {refusal}")
        text = choice.message.content
        if not text:
            raise ModelError(
                ModelError.Kind.API_ERROR,
                f"empty response content (finish_reason={finish!r})",
            )
        usage = resp.usage
        return ModelResponse(
            text=text,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            model_id=self._model,
        )
