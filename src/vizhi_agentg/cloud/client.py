from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import websockets

from ..models import AgentConfig, JobRequest, JobResult, JobStatus


class CloudClient:
    def __init__(self, config: AgentConfig, log_callback=None) -> None:
        self.config = config
        self.log_callback = log_callback or (lambda message: None)

    def _log(self, message: str) -> None:
        self.log_callback(message)

    def _url(self, path: str) -> str:
        return urljoin(self.config.backend_url.rstrip("/") + "/", path.lstrip("/"))

    def _headers(self) -> dict[str, str]:
        headers = {
            "X-Agent-CID": self.config.agent_id,
            "X-Agent-Token": self.config.agent_api_key,
        }
        return headers

    def _ws_url(self) -> str:
        parts = urlsplit(self.config.backend_url)
        scheme = "wss" if parts.scheme == "https" else "ws"
        return urlunsplit((scheme, parts.netloc, self.config.ws_path, "", ""))

    async def register(self) -> dict[str, Any]:
        payload = {
            "agent_id": self.config.agent_id,
            "device_name": self.config.device_name,
            "os_name": "",
            "agent_version": "0.1.0",
            "status": "online",
            "available_engines": [engine.name for engine in self.config.engines if engine.enabled],
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self._url(self.config.register_path),
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def heartbeat(self, state: dict[str, Any]) -> None:
        payload = {
            "agent_id": self.config.agent_id,
            "device_name": self.config.device_name,
            "os_name": "",
            "agent_version": "0.1.0",
            "status": "online",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            **state,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self._url(self.config.heartbeat_path),
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()

    async def fetch_next_job(self) -> JobRequest | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self._url(self.config.jobs_path),
                headers=self._headers(),
            )
            if response.status_code == 204:
                return None
            response.raise_for_status()
            data = response.json()
            if not data:
                return None
            return JobRequest.model_validate(data)

    async def submit_result(self, result: JobResult) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._url(self.config.submit_path),
                json=result.model_dump(mode="json"),
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def websocket_events(self) -> AsyncIterator[dict[str, Any]]:
        ws_url = self._ws_url()
        connect_kwargs = {
            "ping_interval": 20,
            "ping_timeout": 20,
        }
        try:
            connect_kwargs["additional_headers"] = self._headers()
            websocket_cm = websockets.connect(ws_url, **connect_kwargs)
        except TypeError:
            connect_kwargs.pop("additional_headers", None)
            connect_kwargs["extra_headers"] = self._headers()
            websocket_cm = websockets.connect(ws_url, **connect_kwargs)

        async with websocket_cm as websocket:
            await websocket.send(
                json.dumps(
                    {
                        "type": "hello",
                        "agent_id": self.config.agent_id,
                        "device_name": self.config.device_name,
                        "available_engines": [engine.name for engine in self.config.engines if engine.enabled],
                    }
                )
            )
            while True:
                raw = await websocket.recv()
                yield self._coerce_message(raw)

    def _coerce_message(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="ignore")
        if isinstance(raw, str):
            try:
                import json

                return json.loads(raw)
            except Exception:
                return {"type": "message", "raw": raw}
        return {"type": "message", "raw": str(raw)}

    async def reconnecting_websocket(self) -> AsyncIterator[dict[str, Any]]:
        backoff = 2.0
        while True:
            try:
                async for event in self.websocket_events():
                    yield event
                backoff = 2.0
            except Exception as exc:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    @staticmethod
    def completed_result(job_id: str, output: dict[str, Any]) -> JobResult:
        return JobResult(
            job_id=job_id,
            status=JobStatus.completed,
            output=output,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def failed_result(job_id: str, error: str) -> JobResult:
        return JobResult(
            job_id=job_id,
            status=JobStatus.failed,
            error=error,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
