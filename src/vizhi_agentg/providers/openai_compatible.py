from __future__ import annotations

from typing import Any

import httpx

from .base import LocalInferenceProvider


class OpenAICompatibleProvider(LocalInferenceProvider):
    async def health_check(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.endpoint}/v1/models")
            response.raise_for_status()
            return response.json()

    async def list_models(self) -> list[str]:
        payload = await self.health_check()
        return [item.get("id", "") for item in payload.get("data", []) if item.get("id")]

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        body = {
            "model": kwargs.get("model") or self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        return await self.chat(body["messages"], model=body["model"])

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        payload = {"model": kwargs.get("model") or self.model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.endpoint}/v1/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def embeddings(self, text: str, **kwargs: Any) -> dict[str, Any]:
        payload = {"model": kwargs.get("model") or self.model, "input": text}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.endpoint}/v1/embeddings", json=payload)
            response.raise_for_status()
            return response.json()



