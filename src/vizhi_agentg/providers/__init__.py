from __future__ import annotations

from .base import LocalInferenceProvider
from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider


def build_provider(provider_type: str, endpoint: str, model: str = "") -> LocalInferenceProvider:
    key = provider_type.lower()
    if key == "ollama":
        return OllamaProvider(endpoint=endpoint, model=model)
    return OpenAICompatibleProvider(endpoint=endpoint, model=model)

