"""Anthropic model client. Requires `pip install docpatch[anthropic]`."""

from __future__ import annotations

from docpatch.core.errors import ModelError
from docpatch.models.base import ModelResponse

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore[assignment]


class AnthropicClient:
    """Thin wrapper around the Anthropic Messages API."""

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
    ) -> None:
        if _anthropic is None:
            raise ModelError(
                ModelError.Kind.MISSING_EXTRA,
                "Install anthropic extra: pip install docpatch[anthropic]",
            )
        self._model = model
        self._client = _anthropic.Anthropic(api_key=api_key)

    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ModelError(ModelError.Kind.API_ERROR, str(exc)) from exc

        text_blocks = [b for b in msg.content if hasattr(b, "text")]
        text = getattr(text_blocks[0], "text", "") if text_blocks else ""
        return ModelResponse(
            text=text,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
            model_id=self._model,
        )
