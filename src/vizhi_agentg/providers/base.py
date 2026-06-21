from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LocalInferenceProvider(ABC):
    def __init__(self, endpoint: str, model: str = "") -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def list_models(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    async def embeddings(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return {"embedding": [], "text": text, "provider": self.__class__.__name__}
