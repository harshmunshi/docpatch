"""OpenAI model client. Requires `pip install docpatch[openai]`."""

from __future__ import annotations

from docpatch.core.errors import ModelError
from docpatch.models.base import ModelResponse

try:
    import openai as _openai
except ImportError:
    _openai = None  # type: ignore[assignment]


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
        text = choice.message.content or ""
        usage = resp.usage
        return ModelResponse(
            text=text,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            model_id=self._model,
        )
