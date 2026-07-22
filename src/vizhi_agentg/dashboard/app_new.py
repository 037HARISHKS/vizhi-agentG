"""Refactored dashboard app with static frontend and clean JSON APIs."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from aiohttp import web

from .._defaults import resolve_backend_url
from ..models import AgentConfig
from ..service import AgentService


def build_dashboard_app() -> web.Application:
    """Build the dashboard web application."""
    service = AgentService()
    app = web.Application()

    # Get static files directory
    static_dir = Path(__file__).parent / "static"

    # ── Lifecycle ────────────────────────────────────────────────

    async def on_startup(app: web.Application) -> None:
        runtime = service.get_runtime()
        await runtime.start()
        app["queue_task"] = asyncio.create_task(runtime.process_queue())

    async def on_shutdown(app: web.Application) -> None:
        task = app.get("queue_task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        runtime = service.get_runtime()
        await runtime.stop()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # ── Routes ───────────────────────────────────────────────────

    async def serve_index(request: web.Request) -> web.Response:
        """Serve the main dashboard HTML page."""
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return web.Response(text="Dashboard not found", status=404)
        return web.FileResponse(index_path)

    async def api_config_get(request: web.Request) -> web.Response:
        """Get current configuration."""
        config = service.get_config()
        return web.json_response(config.model_dump(mode="json"))

    async def api_config_post(request: web.Request) -> web.Response:
        """Save new configuration."""
        payload = await request.json()
        current_config = service.get_config()
        
        try:
            # Merge with current config
            merged = current_config.model_dump(mode="json")
            merged.update(payload)
            merged["device_name"] = ""
            merged.pop("backend_url", None)
            merged["backend_url"] = resolve_backend_url()
            merged["poll_interval_idle"] = int(merged.get("poll_interval_idle", current_config.poll_interval_idle))
            merged["poll_interval_busy"] = int(merged.get("poll_interval_busy", current_config.poll_interval_busy))
            merged["dashboard_port"] = int(merged.get("dashboard_port", current_config.dashboard_port))

            # Handle engine model update
            engine_model = str(merged.pop("engine_model", "")).strip()
            default_engine = str(merged.get("default_engine", current_config.default_engine)).strip()
            merged["default_engine"] = default_engine

            engines = []
            for engine in current_config.engines:
                data = engine.model_dump(mode="json")
                engine_name_normalized = engine.name.lower().replace(" ", "_")
                default_engine_normalized = default_engine.lower().replace(" ", "_")
                if engine_name_normalized == default_engine_normalized:
                    data["model"] = engine_model or data["model"]
                engines.append(data)
            merged["engines"] = engines

            new_config = AgentConfig.model_validate(merged)
            service.save_config(new_config)
            
            return web.json_response({"ok": True})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=422)

    async def api_status(request: web.Request) -> web.Response:
        """Get current runtime status."""
        runtime = service.get_runtime()
        data = runtime.snapshot().model_dump(mode="json")
        return web.json_response(data)

    async def api_start(request: web.Request) -> web.Response:
        """Start the agent."""
        runtime = service.get_runtime()
        await runtime.start()
        return web.json_response({"ok": True})

    async def api_stop(request: web.Request) -> web.Response:
        """Stop the agent."""
        runtime = service.get_runtime()
        await runtime.stop()
        return web.json_response({"ok": True})

    async def api_test_engine(request: web.Request) -> web.Response:
        """Test the configured engine."""
        try:
            result = await service.test_engine_isolated()
            return web.json_response({"ok": True, "result": result})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    async def api_logs(request: web.Request) -> web.Response:
        """Get engine logs."""
        logs = service.store.get_logs(limit=50)
        return web.json_response({"logs": logs})

    async def api_jobs(request: web.Request) -> web.Response:
        """Get job history."""
        jobs = service.store.get_job_history(limit=30)
        return web.json_response({"jobs": jobs})

    # Register routes
    app.router.add_get("/", serve_index)
    app.router.add_get("/api/config", api_config_get)
    app.router.add_post("/api/config", api_config_post)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/start", api_start)
    app.router.add_post("/api/stop", api_stop)
    app.router.add_get("/api/test-engine", api_test_engine)
    app.router.add_get("/api/logs", api_logs)
    app.router.add_get("/api/jobs", api_jobs)

    # Serve static files
    app.router.add_static("/static", static_dir, name="static")

    return app
