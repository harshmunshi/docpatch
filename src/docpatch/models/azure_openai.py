"""Azure OpenAI Service client. Requires pip install docpatch[azure]."""

from __future__ import annotations

from typing import Any

from docpatch.core.errors import ModelError
from docpatch.models.base import ModelResponse


class AzureOpenAIClient:
    """Wraps openai.AzureOpenAI — supports API-key and Azure AD (Entra ID) auth.

    Args:
        deployment:     Azure deployment name (the model alias you created in the portal).
        azure_endpoint: Resource endpoint, e.g. "https://my-res.openai.azure.com/".
        api_version:    Azure OpenAI API version, e.g. "2024-02-01".
        api_key:        Azure OpenAI key. Omit to use Azure AD via DefaultAzureCredential.
    """

    _client: Any

    def __init__(
        self,
        deployment: str,
        azure_endpoint: str,
        api_version: str = "2024-02-01",
        api_key: str | None = None,
    ) -> None:
        try:
            import openai as _oai
        except ImportError:
            raise ModelError(
                ModelError.Kind.MISSING_EXTRA,
                "Install azure extra: pip install docpatch[azure]",
            ) from None

        if api_key:
            self._client = _oai.AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_version=api_version,
                api_key=api_key,
            )
        else:
            # Azure AD (Entra ID) token auth via azure-identity
            try:
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            except ImportError:
                raise ModelError(
                    ModelError.Kind.MISSING_EXTRA,
                    "Install azure extra for AD auth: pip install docpatch[azure]",
                ) from None
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            self._client = _oai.AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_version=api_version,
                azure_ad_token_provider=token_provider,
            )

        self._deployment = deployment

    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        try:
            resp = self._client.chat.completions.create(
                model=self._deployment,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ModelError(ModelError.Kind.API_ERROR, str(exc)) from exc

        choice = resp.choices[0]
        finish = getattr(choice, "finish_reason", None)
        if finish == "content_filter":
            raise ModelError(ModelError.Kind.API_ERROR, "response blocked by content filter")
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
            model_id=self._deployment,
        )
