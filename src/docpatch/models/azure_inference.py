"""Azure AI Inference client (Azure AI Foundry / "azure universe").

Covers any model deployed on an Azure AI Foundry serverless or managed endpoint:
Llama, Phi, Mistral, Cohere, and others — using the azure-ai-inference SDK.

Requires pip install docpatch[azure-inference].
"""

from __future__ import annotations

from typing import Any

from docpatch.core.errors import ModelError
from docpatch.models.base import ModelResponse


class AzureInferenceClient:
    """Wraps azure.ai.inference.ChatCompletionsClient.

    Args:
        endpoint: Serverless or managed endpoint URL from Azure AI Foundry,
                  e.g. "https://my-model.eastus.inference.ai.azure.com".
        model:    Optional model name; required for multi-model endpoints.
        api_key:  Inference API key. Omit to use Azure AD via DefaultAzureCredential.
    """

    _client: Any

    def __init__(
        self,
        endpoint: str,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        try:
            from azure.ai.inference import ChatCompletionsClient
            from azure.ai.inference.models import SystemMessage, UserMessage  # noqa: F401
        except ImportError:
            raise ModelError(
                ModelError.Kind.MISSING_EXTRA,
                "Install azure-inference extra: pip install docpatch[azure-inference]",
            ) from None

        if api_key:
            try:
                from azure.core.credentials import AzureKeyCredential
            except ImportError:
                raise ModelError(
                    ModelError.Kind.MISSING_EXTRA,
                    "Install azure-inference extra: pip install docpatch[azure-inference]",
                ) from None
            credential: Any = AzureKeyCredential(api_key)
        else:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError:
                raise ModelError(
                    ModelError.Kind.MISSING_EXTRA,
                    "Install azure extra for AD auth: pip install docpatch[azure]",
                ) from None
            credential = DefaultAzureCredential()

        self._client = ChatCompletionsClient(endpoint=endpoint, credential=credential)
        self._model = model

    def complete(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        try:
            from azure.ai.inference.models import UserMessage
        except ImportError:
            raise ModelError(
                ModelError.Kind.MISSING_EXTRA,
                "Install azure-inference extra: pip install docpatch[azure-inference]",
            ) from None

        kwargs: dict[str, Any] = {
            "messages": [UserMessage(content=prompt)],
            "max_tokens": max_tokens,
        }
        if self._model:
            kwargs["model"] = self._model

        try:
            resp = self._client.complete(**kwargs)
        except Exception as exc:
            raise ModelError(ModelError.Kind.API_ERROR, str(exc)) from exc

        choice = resp.choices[0]
        text = choice.message.content
        if not text:
            raise ModelError(
                ModelError.Kind.API_ERROR,
                f"empty response (finish_reason={choice.finish_reason!r})",
            )
        usage = getattr(resp, "usage", None)
        return ModelResponse(
            text=text,
            tokens_in=getattr(usage, "prompt_tokens", 0),
            tokens_out=getattr(usage, "completion_tokens", 0),
            model_id=self._model or "",
        )
