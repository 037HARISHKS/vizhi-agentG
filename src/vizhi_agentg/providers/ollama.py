from __future__ import annotations

from typing import Any

import httpx

from .base import LocalInferenceProvider


class OllamaProvider(LocalInferenceProvider):
    async def health_check(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.endpoint}/api/tags")
            response.raise_for_status()
            return response.json()

    async def list_models(self) -> list[str]:
        payload = await self.health_check()
        return [model.get("name", "") for model in payload.get("models", []) if model.get("name")]

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        payload = {"model": kwargs.get("model") or self.model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.endpoint}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        payload = {"model": kwargs.get("model") or self.model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.endpoint}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
