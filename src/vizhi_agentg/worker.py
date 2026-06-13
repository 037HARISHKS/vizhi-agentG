from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

from .cloud.client import CloudClient
from .models import (
    AgentConfig,
    AgentRuntimeState,
    EngineConfig,
    JobRequest,
    JobResult,
    JobStatus,
    StatusSnapshot,
)
from .providers import build_provider


class AgentRuntime:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.state = AgentRuntimeState()
        self._started_at = datetime.now(timezone.utc)
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[JobRequest] = asyncio.Queue()
        self._recent_logs = deque(maxlen=200)
        self.cloud = CloudClient(config, log_callback=self.log)

    def log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        line = f"[{stamp}] {message}"
        self._recent_logs.appendleft(line)
        self.state.logs = list(self._recent_logs)

    def _resolve_engine(self, name: str | None) -> EngineConfig:
        engine_name = (name or self.config.default_engine).strip()
        for engine in self.config.engines:
            if engine.enabled and engine.name.lower() == engine_name.lower():
                return engine
        for engine in self.config.engines:
            if engine.enabled:
                return engine
        raise ValueError("No enabled inference engines are configured")

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.state.connected = False
        self.state.websocket_connected = False

    async def _run(self) -> None:
        self.state.connected = True
        try:
            await self.cloud.register()
        except Exception as exc:
            pass

        websocket_task = asyncio.create_task(self._run_websocket())
        polling_task = asyncio.create_task(self._run_polling())
        heartbeat_task = asyncio.create_task(self._run_heartbeat())

        try:
            await self._stop_event.wait()
        finally:
            for task in (websocket_task, polling_task, heartbeat_task):
                task.cancel()
            await asyncio.gather(websocket_task, polling_task, heartbeat_task, return_exceptions=True)

    async def _run_websocket(self) -> None:
        if not self.config.enable_websocket:
            return
        async for event in self.cloud.reconnecting_websocket():
            if self._stop_event.is_set():
                break
            event_type = str(event.get("type", "")).lower()
            if event_type in {"job", "job_created", "job.ready", "job_available"}:
                job = await self.cloud.fetch_next_job()
                if job:
                    await self._queue.put(job)
                    self.state.queue_depth = self._queue.qsize()
                self.state.websocket_connected = True
            elif event_type in {"heartbeat", "connected", "pong"}:
                self.state.websocket_connected = True
            elif event_type == "shutdown":
                self._stop_event.set()
                return

    async def _run_polling(self) -> None:
        if not self.config.enable_polling:
            return
        while not self._stop_event.is_set():
            try:
                job = await self.cloud.fetch_next_job()
                if job:
                    await self._queue.put(job)
                    self.state.queue_depth = self._queue.qsize()
                    await asyncio.sleep(self.config.poll_interval_busy)
                else:
                    await asyncio.sleep(self.config.poll_interval_idle)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await asyncio.sleep(self.config.poll_interval_idle)

    async def _run_heartbeat(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.state.last_heartbeat = datetime.now(timezone.utc).isoformat()
                await self.cloud.heartbeat(
                    {
                        "active_engine": self.state.active_engine,
                        "active_job_id": self.state.active_job_id,
                        "queue_depth": self._queue.qsize(),
                        "state": "running" if self.state.active_job_id else "idle",
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                pass
            await asyncio.sleep(30)

    async def process_queue(self) -> None:
        while not self._stop_event.is_set():
            job = await self._queue.get()
            self.state.queue_depth = self._queue.qsize()
            self.state.active_job_id = job.id
            self.log(f"processing job {job.id} with {job.model or self.state.active_engine}")
            try:
                result = await self.handle_job(job)
                self.state.total_completed += 1
                self.state.job_history.insert(0, result.model_dump(mode="json"))
                await self.cloud.submit_result(result)
                self.log(f"job {job.id} completed")
            except Exception as exc:
                self.state.total_failed += 1
                failure = self.cloud.failed_result(job.id, str(exc))
                self.state.job_history.insert(0, failure.model_dump(mode="json"))
                try:
                    await self.cloud.submit_result(failure)
                except Exception as submit_exc:
                    self.log(f"failed to submit failure for {job.id}: {submit_exc}")
                self.log(f"job {job.id} failed: {exc}")
            finally:
                self.state.active_job_id = ""
                self._queue.task_done()

    async def handle_job(self, job: JobRequest) -> JobResult:
        engine = self._resolve_engine(job.engine)
        provider = build_provider(
            engine.provider_type.value if hasattr(engine.provider_type, "value") else str(engine.provider_type),
            engine.endpoint,
            engine.model,
        )
        self.state.active_engine = engine.name
        payload = job.input or {}
        kind = job.kind.lower()
        if kind == "chat":
            messages = payload.get("messages") or []
            output = await provider.chat(messages, model=job.model or engine.model)
        elif kind == "generate":
            prompt = str(payload.get("prompt", ""))
            output = await provider.generate(prompt, model=job.model or engine.model)
        elif kind == "embeddings":
            text = str(payload.get("text", ""))
            output = await provider.embeddings(text, model=job.model or engine.model)
        else:
            raise ValueError(f"Unsupported job kind: {job.kind}")

        self.log(f"{engine.name}: {kind} completed")
        return self.cloud.completed_result(job.id, output)

    def snapshot(self) -> StatusSnapshot:
        uptime = int((datetime.now(timezone.utc) - self._started_at).total_seconds())
        return StatusSnapshot(
            agent_id=self.config.agent_id,
            device_name=self.config.device_name,
            backend_url=self.config.backend_url,
            connected=self.state.connected,
            websocket_connected=self.state.websocket_connected,
            last_heartbeat=self.state.last_heartbeat,
            active_engine=self.state.active_engine,
            active_job_id=self.state.active_job_id,
            queue_depth=self._queue.qsize(),
            total_completed=self.state.total_completed,
            total_failed=self.state.total_failed,
            uptime_seconds=uptime,
            available_engines=[engine.name for engine in self.config.engines if engine.enabled],
            logs=list(self.state.logs),
        )

    def update_config(self, config: AgentConfig) -> None:
        self.config = config
        self.cloud = CloudClient(config, log_callback=self.log)

    def enqueue_job(self, job: JobRequest) -> None:
        self._queue.put_nowait(job)
        self.state.queue_depth = self._queue.qsize()

    async def test_engine(self, engine_name: str) -> dict[str, Any]:
        engine = self._resolve_engine(engine_name)
        provider = build_provider(engine.provider_type.value, engine.endpoint, engine.model)
        result = await provider.health_check()
        self.log(f"{engine.name}: health check passed")
        return result
