from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ..models import AgentConfig, EngineConfig
from ..storage import FileStore
from ..worker import AgentRuntime


def build_dashboard_app() -> FastAPI:
    store = FileStore()
    config = store.load_config()
    runtime = AgentRuntime(config)
    app = FastAPI(title="Vizhi AgentG", version="0.1.0")

    @app.on_event("startup")
    async def _startup() -> None:
        await runtime.start()
        app.state.queue_task = asyncio.create_task(runtime.process_queue())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        task = getattr(app.state, "queue_task", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await runtime.stop()

    @app.get("/", response_class=HTMLResponse)
    async def home() -> str:
        snapshot = runtime.snapshot()
        selected_engine = next(
            (engine for engine in config.engines if engine.name.lower() == config.default_engine.lower()),
            config.engines[0],
        )
        engine_value = "lm_studio" if selected_engine.name.lower().startswith("lm") else "ollama"
        logs = "<br>".join(snapshot.logs[:20]) or "No engine logs yet"
        html = f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <title>Vizhi AgentG</title>
            <style>
              :root {{
                color-scheme: dark;
                --bg: #0b1220;
                --panel: #111a2b;
                --panel-2: #0f1726;
                --line: #243044;
                --text: #e5eef9;
                --muted: #9fb0c7;
                --accent: #58d0a8;
              }}
              * {{ box-sizing: border-box; }}
              body {{
                margin: 0;
                font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: radial-gradient(circle at top, #121c31 0, var(--bg) 45%);
                color: var(--text);
              }}
              .wrap {{
                max-width: 1120px;
                margin: 0 auto;
                padding: 32px 18px 40px;
              }}
              .eyebrow {{
                font-size: 13px;
                color: var(--muted);
                margin: 0 0 10px;
              }}
              h1 {{
                margin: 0;
                font-size: 34px;
                line-height: 1.1;
                letter-spacing: 0;
              }}
              .sub {{
                margin: 12px 0 0;
                color: var(--muted);
                max-width: 760px;
              }}
              .panel {{
                margin-top: 22px;
                padding: 18px;
                border: 1px solid var(--line);
                border-radius: 12px;
                background: rgba(17, 26, 43, 0.92);
                box-shadow: 0 18px 60px rgba(0, 0, 0, 0.22);
              }}
              .title {{
                margin: 0 0 14px;
                font-size: 18px;
              }}
              .form {{
                display: grid;
                grid-template-columns: 1.2fr 1fr 1fr auto;
                gap: 12px;
                align-items: end;
              }}
              .field label {{
                display: block;
                font-size: 12px;
                color: var(--muted);
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.04em;
              }}
              input, select, button {{
                width: 100%;
                padding: 11px 12px;
                border-radius: 10px;
                border: 1px solid var(--line);
                background: var(--panel-2);
                color: var(--text);
                outline: none;
              }}
              input::placeholder {{ color: #6f7f97; }}
              button {{
                cursor: pointer;
                background: var(--accent);
                color: #07131b;
                font-weight: 700;
                border-color: transparent;
                white-space: nowrap;
              }}
              .note {{
                margin-top: 10px;
                color: var(--muted);
                font-size: 13px;
              }}
              .logs {{
                white-space: pre-wrap;
                font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                font-size: 13px;
                line-height: 1.55;
                color: #dbe6f3;
                min-height: 220px;
              }}
              @media (max-width: 900px) {{
                .form {{ grid-template-columns: 1fr; }}
              }}
            </style>
          </head>
          <body>
            <div class="wrap">
              <p class="eyebrow">Vizhi AgentG</p>
              <h1>Local Agent Setup</h1>
              <p class="sub">Connect this machine to Vizhi with the agent CID and API key. The agent will run on localhost and route jobs to Ollama or LM Studio.</p>

              <section class="panel">
                <h2 class="title">Agent Connection</h2>
                <form id="config-form" class="form">
                  <div class="field">
                    <label>Agent CID</label>
                    <input name="agent_id" value="{config.agent_id}" placeholder="ag_xxxxxxxx" />
                  </div>
                  <div class="field">
                    <label>Agent API Key</label>
                    <input name="agent_api_key" value="{config.agent_api_key}" placeholder="vz_live_..." type="password" />
                  </div>
                  <div class="field">
                    <label>Engine</label>
                    <select name="default_engine">
                      <option value="ollama" {"selected" if engine_value == "ollama" else ""}>Ollama</option>
                      <option value="lm_studio" {"selected" if engine_value == "lm_studio" else ""}>LM Studio</option>
                    </select>
                  </div>
                  <div class="field">
                    <label>Model</label>
                    <input name="engine_model" value="{selected_engine.model}" placeholder="llama3.1" />
                  </div>
                  <button type="submit">Save</button>
                </form>
                <div class="note">All endpoints stay local. Ollama uses <code>http://127.0.0.1:11434</code> and LM Studio uses <code>http://127.0.0.1:1234</code>.</div>
              </section>

              <section class="panel">
                <h2 class="title">Engine Logs</h2>
                <div class="logs">{logs}</div>
              </section>
            </div>

            <script>
              async function postJson(url, body) {{
                const res = await fetch(url, {{
                  method: 'POST',
                  headers: {{ 'Content-Type': 'application/json' }},
                  body: JSON.stringify(body)
                }});
                if (!res.ok) throw new Error(await res.text());
                return res.json().catch(() => ({{}}));
              }}

              document.getElementById('config-form').addEventListener('submit', async (event) => {{
                event.preventDefault();
                const form = new FormData(event.target);
                await postJson('/api/config', Object.fromEntries(form.entries()));
                location.reload();
              }});
            </script>
          </body>
        </html>
        """
        return html

    @app.get("/api/status")
    async def status() -> dict:
        return runtime.snapshot().model_dump(mode="json")

    @app.post("/api/start")
    async def start_agent() -> dict:
        await runtime.start()
        return {"ok": True}

    @app.post("/api/stop")
    async def stop_agent() -> dict:
        await runtime.stop()
        return {"ok": True}

    @app.post("/api/config")
    async def update_config(payload: dict) -> dict:
        nonlocal config
        try:
            merged = config.model_dump(mode="json")
            merged.update(payload)
            merged["device_name"] = ""
            merged["backend_url"] = "http://127.0.0.1:8000"
            merged["poll_interval_idle"] = int(merged.get("poll_interval_idle", config.poll_interval_idle))
            merged["poll_interval_busy"] = int(merged.get("poll_interval_busy", config.poll_interval_busy))
            merged["dashboard_port"] = int(merged.get("dashboard_port", config.dashboard_port))
            engine_model = str(merged.pop("engine_model", "")).strip()
            default_engine = str(merged.get("default_engine", config.default_engine)).strip()
            merged["default_engine"] = default_engine
            engines = []
            for engine in config.engines:
                data = engine.model_dump(mode="json")
                if engine.name.lower() == default_engine.lower():
                    data["model"] = engine_model or data["model"]
                engines.append(data)
            merged["engines"] = engines
            new_config = AgentConfig.model_validate(merged)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        store.save_config(new_config)
        runtime.update_config(new_config)
        config = new_config
        return {"ok": True}

    return app
