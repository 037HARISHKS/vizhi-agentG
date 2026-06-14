from __future__ import annotations

import asyncio
import json

from aiohttp import web

from ..models import AgentConfig, EngineConfig
from ..storage import SQLiteStore
from ..worker import AgentRuntime


# ─────────────────────────────────────────────────────────────────
#  HTML Template
# ─────────────────────────────────────────────────────────────────

def _render_html(config: AgentConfig, runtime: AgentRuntime, store: SQLiteStore) -> str:
    snapshot = runtime.snapshot()
    selected_engine = next(
        (e for e in config.engines if e.name.lower() == config.default_engine.lower()),
        config.engines[0],
    )
    engine_value = "lm_studio" if selected_engine.name.lower().startswith("lm") else "ollama"

    # Build log lines from DB
    db_logs = store.get_logs(limit=30)
    log_lines = "".join(
        f'<div class="log-line"><span class="log-ts">{l["timestamp"]}</span>{l["message"]}</div>'
        for l in db_logs
    ) or '<div class="log-empty">No engine logs yet</div>'

    # Build job history rows
    jobs = store.get_job_history(limit=15)
    job_rows = ""
    for j in jobs:
        status_cls = "st-ok" if j["status"] == "completed" else "st-err"
        job_rows += (
            f'<tr>'
            f'<td class="mono">{j["job_id"][:16]}</td>'
            f'<td><span class="badge {status_cls}">{j["status"]}</span></td>'
            f'<td>{j["completed_at"][:19] if j["completed_at"] else "—"}</td>'
            f'<td class="mono">{j["error"][:40] if j["error"] else "—"}</td>'
            f'</tr>'
        )
    if not job_rows:
        job_rows = '<tr><td colspan="4" class="empty-row">No jobs processed yet</td></tr>'

    conn_cls = "indicator-on" if snapshot.connected else "indicator-off"
    ws_cls = "indicator-on" if snapshot.websocket_connected else "indicator-off"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vizhi AgentG</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0a0e1a;--surface:#12182b;--surface2:#181f35;--border:#243044;
  --text:#e8edf5;--muted:#8899af;--accent:#6ee7b7;--accent2:#34d399;
  --danger:#f87171;--radius:14px;--shadow:0 8px 32px rgba(0,0,0,.35);
}}
html{{font-size:15px}}
body{{
  font-family:'Inter','Segoe UI',system-ui,-apple-system,sans-serif;
  background:var(--bg);color:var(--text);min-height:100vh;
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -10%,rgba(110,231,183,.07),transparent),
    radial-gradient(ellipse 60% 40% at 80% 100%,rgba(56,189,248,.05),transparent);
}}
a{{color:var(--accent);text-decoration:none}}

/* ── Layout ── */
.shell{{max-width:1060px;margin:0 auto;padding:28px 20px 48px}}
.brand{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}
.brand svg{{width:28px;height:28px}}
.brand span{{font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}}
h1{{font-size:28px;font-weight:700;letter-spacing:-.01em;line-height:1.2}}
.subtitle{{color:var(--muted);margin:8px 0 0;max-width:640px;line-height:1.55}}

/* ── Status Bar ── */
.status-bar{{
  display:flex;flex-wrap:wrap;gap:16px;margin:22px 0 18px;
  padding:14px 18px;border-radius:var(--radius);
  background:var(--surface);border:1px solid var(--border);
}}
.stat{{display:flex;align-items:center;gap:8px;font-size:13px}}
.stat .label{{color:var(--muted)}}
.stat .value{{font-weight:600}}
.indicator{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.indicator-on{{background:var(--accent);box-shadow:0 0 6px var(--accent)}}
.indicator-off{{background:#475569}}

/* ── Cards ── */
.grid{{display:grid;grid-template-columns:1fr;gap:18px;margin-top:18px}}
@media(min-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}
.card{{
  padding:20px 22px;border-radius:var(--radius);
  background:var(--surface);border:1px solid var(--border);
  box-shadow:var(--shadow);
}}
.card-full{{grid-column:1/-1}}
.card-title{{
  font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
  color:var(--accent);margin-bottom:16px;display:flex;align-items:center;gap:8px;
}}
.card-title svg{{width:18px;height:18px;opacity:.7}}

/* ── Form ── */
.form-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:600px){{.form-grid{{grid-template-columns:1fr}}}}
.field{{display:flex;flex-direction:column;gap:6px}}
.field label{{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}
.field input,.field select{{
  padding:10px 12px;border-radius:10px;border:1px solid var(--border);
  background:var(--surface2);color:var(--text);font-size:14px;
  outline:none;transition:border-color .2s;
}}
.field input:focus,.field select:focus{{border-color:var(--accent)}}
.field input::placeholder{{color:#556677}}
.btn-row{{display:flex;gap:10px;margin-top:16px}}
.btn{{
  padding:10px 28px;border-radius:10px;border:none;cursor:pointer;
  font-size:14px;font-weight:700;transition:all .2s;
}}
.btn-primary{{background:var(--accent);color:#071a12}}
.btn-primary:hover{{background:var(--accent2);transform:translateY(-1px)}}
.btn-secondary{{background:var(--surface2);color:var(--text);border:1px solid var(--border)}}
.btn-secondary:hover{{border-color:var(--accent)}}

/* ── Logs ── */
.log-box{{
  max-height:260px;overflow-y:auto;padding:12px 14px;
  border-radius:10px;background:var(--bg);border:1px solid var(--border);
  font-family:'JetBrains Mono','Fira Code',ui-monospace,monospace;font-size:12.5px;line-height:1.7;
}}
.log-box::-webkit-scrollbar{{width:6px}}
.log-box::-webkit-scrollbar-thumb{{background:#334155;border-radius:3px}}
.log-line{{display:flex;gap:10px;color:#c8d6e5}}
.log-ts{{color:#64748b;flex-shrink:0}}
.log-empty{{color:var(--muted);font-style:italic}}

/* ── Table ── */
.tbl{{width:100%;border-collapse:collapse;font-size:13px}}
.tbl th{{
  text-align:left;padding:8px 10px;font-size:11px;font-weight:600;
  text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
  border-bottom:1px solid var(--border);
}}
.tbl td{{padding:8px 10px;border-bottom:1px solid rgba(36,48,68,.5)}}
.tbl tr:last-child td{{border-bottom:none}}
.mono{{font-family:ui-monospace,monospace;font-size:12px}}
.badge{{
  display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:.03em;
}}
.st-ok{{background:rgba(110,231,183,.15);color:var(--accent)}}
.st-err{{background:rgba(248,113,113,.15);color:var(--danger)}}
.empty-row{{color:var(--muted);text-align:center;font-style:italic;padding:20px!important}}

/* ── Toast ── */
.toast{{
  position:fixed;bottom:24px;right:24px;padding:12px 22px;border-radius:10px;
  background:var(--accent);color:#071a12;font-weight:700;font-size:14px;
  box-shadow:0 6px 20px rgba(0,0,0,.3);transform:translateY(80px);opacity:0;
  transition:all .35s ease;pointer-events:none;z-index:999;
}}
.toast.show{{transform:translateY(0);opacity:1}}

/* ── Metrics row ── */
.metrics{{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:16px}}
.metric{{
  flex:1;min-width:100px;padding:14px 16px;border-radius:12px;
  background:var(--surface2);border:1px solid var(--border);text-align:center;
}}
.metric .m-val{{font-size:26px;font-weight:800;color:var(--accent)}}
.metric .m-lbl{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:4px}}
</style>
</head>
<body>
<div class="shell">

  <!-- Header -->
  <div class="brand">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--accent)"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
    <span>Vizhi AgentG</span>
  </div>
  <h1>Local Agent Dashboard</h1>
  <p class="subtitle">Configure your local inference agent, monitor engine activity, and track job history — all from one place.</p>

  <!-- Status Bar -->
  <div class="status-bar">
    <div class="stat"><div class="indicator {conn_cls}"></div><span class="label">Agent</span><span class="value">{snapshot.agent_id}</span></div>
    <div class="stat"><div class="indicator {conn_cls}"></div><span class="label">Connected</span><span class="value">{"Yes" if snapshot.connected else "No"}</span></div>
    <div class="stat"><div class="indicator {ws_cls}"></div><span class="label">WebSocket</span><span class="value">{"Live" if snapshot.websocket_connected else "Off"}</span></div>
    <div class="stat"><span class="label">Engine</span><span class="value">{snapshot.active_engine or "idle"}</span></div>
    <div class="stat"><span class="label">Uptime</span><span class="value">{snapshot.uptime_seconds // 60}m {snapshot.uptime_seconds % 60}s</span></div>
  </div>

  <div class="grid">

    <!-- Config Card -->
    <div class="card">
      <div class="card-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
        Agent Connection
      </div>
      <form id="cfg-form">
        <div class="form-grid">
          <div class="field">
            <label>Agent CID</label>
            <input name="agent_id" value="{config.agent_id}" placeholder="ag_xxxxxxxx"/>
          </div>
          <div class="field">
            <label>API Key</label>
            <input name="agent_api_key" value="{config.agent_api_key}" type="password" placeholder="vz_live_..."/>
          </div>
          <div class="field">
            <label>Engine</label>
            <select name="default_engine">
              <option value="ollama" {"selected" if engine_value=="ollama" else ""}>Ollama</option>
              <option value="lm_studio" {"selected" if engine_value=="lm_studio" else ""}>LM Studio</option>
            </select>
          </div>
          <div class="field">
            <label>Model</label>
            <input name="engine_model" value="{selected_engine.model}" placeholder="llama3.1"/>
          </div>
        </div>
        <div class="btn-row">
          <button type="submit" class="btn btn-primary">Save Configuration</button>
          <button type="button" class="btn btn-secondary" onclick="testEngine()">Test Engine</button>
        </div>
      </form>
      <p style="margin-top:12px;font-size:12px;color:var(--muted)">
        Ollama &rarr; <code>127.0.0.1:11434</code> &nbsp;&middot;&nbsp; LM Studio &rarr; <code>127.0.0.1:1234</code>
      </p>
    </div>

    <!-- Metrics Card -->
    <div class="card">
      <div class="card-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
        Metrics
      </div>
      <div class="metrics">
        <div class="metric"><div class="m-val">{snapshot.total_completed}</div><div class="m-lbl">Completed</div></div>
        <div class="metric"><div class="m-val">{snapshot.total_failed}</div><div class="m-lbl">Failed</div></div>
        <div class="metric"><div class="m-val">{snapshot.queue_depth}</div><div class="m-lbl">Queued</div></div>
      </div>
      <div style="font-size:13px;color:var(--muted)">
        <div style="margin-bottom:6px"><strong style="color:var(--text)">Available Engines:</strong></div>
        {", ".join(snapshot.available_engines) or "None configured"}
      </div>
      <div class="btn-row" style="margin-top:18px">
        <button class="btn btn-primary" onclick="controlAgent('start')" style="flex:1">Start Agent</button>
        <button class="btn btn-secondary" onclick="controlAgent('stop')" style="flex:1">Stop Agent</button>
      </div>
    </div>

    <!-- Logs Card -->
    <div class="card card-full">
      <div class="card-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        Engine Logs
        <button class="btn btn-secondary" onclick="refreshLogs()" style="margin-left:auto;padding:5px 14px;font-size:12px">Refresh</button>
      </div>
      <div class="log-box" id="log-box">{log_lines}</div>
    </div>

    <!-- Job History Card -->
    <div class="card card-full">
      <div class="card-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
        Job History
      </div>
      <div style="overflow-x:auto">
        <table class="tbl">
          <thead><tr><th>Job ID</th><th>Status</th><th>Completed</th><th>Error</th></tr></thead>
          <tbody>{job_rows}</tbody>
        </table>
      </div>
    </div>

  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
function toast(msg, ok) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = ok ? 'var(--accent)' : 'var(--danger)';
  t.style.color = ok ? '#071a12' : '#fff';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}}

async function postJson(url, body) {{
  const res = await fetch(url, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body || {{}})
  }});
  if (!res.ok) throw new Error(await res.text());
  return res.json().catch(() => ({{}}));
}}

document.getElementById('cfg-form').addEventListener('submit', async (e) => {{
  e.preventDefault();
  try {{
    const fd = new FormData(e.target);
    await postJson('/api/config', Object.fromEntries(fd.entries()));
    toast('Configuration saved!', true);
    setTimeout(() => location.reload(), 800);
  }} catch (err) {{
    toast('Save failed: ' + err.message, false);
  }}
}});

async function controlAgent(action) {{
  try {{
    await postJson('/api/' + action);
    toast('Agent ' + action + ' successful', true);
    setTimeout(() => location.reload(), 1000);
  }} catch (err) {{
    toast(action + ' failed: ' + err.message, false);
  }}
}}

async function testEngine() {{
  try {{
    const res = await fetch('/api/test-engine');
    const data = await res.json();
    if (data.ok) toast('Engine OK!', true);
    else toast('Engine error: ' + (data.error || 'unknown'), false);
  }} catch (err) {{
    toast('Engine test failed', false);
  }}
}}

async function refreshLogs() {{
  try {{
    const res = await fetch('/api/logs');
    const data = await res.json();
    const box = document.getElementById('log-box');
    if (data.logs && data.logs.length) {{
      box.innerHTML = data.logs.map(l =>
        '<div class="log-line"><span class="log-ts">' + l.timestamp + '</span>' + l.message + '</div>'
      ).join('');
    }} else {{
      box.innerHTML = '<div class="log-empty">No engine logs yet</div>';
    }}
  }} catch (err) {{
    toast('Failed to refresh logs', false);
  }}
}}

// Auto-refresh logs every 10s
setInterval(refreshLogs, 10000);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
#  aiohttp Application Builder
# ─────────────────────────────────────────────────────────────────

def build_dashboard_app() -> web.Application:
    store = SQLiteStore()
    config = store.load_config()
    runtime = AgentRuntime(config)

    # Shared mutable state
    state: dict = {"config": config}

    app = web.Application()

    # ── lifecycle ────────────────────────────────────────────────

    async def on_startup(app: web.Application) -> None:
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
        await runtime.stop()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # ── routes ───────────────────────────────────────────────────

    async def home(request: web.Request) -> web.Response:
        html = _render_html(state["config"], runtime, store)
        return web.Response(text=html, content_type="text/html")

    async def api_status(request: web.Request) -> web.Response:
        data = runtime.snapshot().model_dump(mode="json")
        return web.json_response(data)

    async def api_start(request: web.Request) -> web.Response:
        await runtime.start()
        return web.json_response({"ok": True})

    async def api_stop(request: web.Request) -> web.Response:
        await runtime.stop()
        return web.json_response({"ok": True})

    async def api_config(request: web.Request) -> web.Response:
        payload = await request.json()
        cfg = state["config"]
        try:
            merged = cfg.model_dump(mode="json")
            merged.update(payload)
            merged["device_name"] = ""
            merged["backend_url"] = "http://127.0.0.1:8000"
            merged["poll_interval_idle"] = int(merged.get("poll_interval_idle", cfg.poll_interval_idle))
            merged["poll_interval_busy"] = int(merged.get("poll_interval_busy", cfg.poll_interval_busy))
            merged["dashboard_port"] = int(merged.get("dashboard_port", cfg.dashboard_port))

            engine_model = str(merged.pop("engine_model", "")).strip()
            default_engine = str(merged.get("default_engine", cfg.default_engine)).strip()
            merged["default_engine"] = default_engine

            engines = []
            for engine in cfg.engines:
                data = engine.model_dump(mode="json")
                if engine.name.lower() == default_engine.lower():
                    data["model"] = engine_model or data["model"]
                engines.append(data)
            merged["engines"] = engines

            new_config = AgentConfig.model_validate(merged)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=422)

        store.save_config(new_config)
        runtime.update_config(new_config)
        state["config"] = new_config
        return web.json_response({"ok": True})

    async def api_logs(request: web.Request) -> web.Response:
        logs = store.get_logs(limit=50)
        return web.json_response({"logs": logs})

    async def api_test_engine(request: web.Request) -> web.Response:
        try:
            result = await runtime.test_engine(state["config"].default_engine)
            return web.json_response({"ok": True, "result": result})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    async def api_jobs(request: web.Request) -> web.Response:
        jobs = store.get_job_history(limit=30)
        return web.json_response({"jobs": jobs})

    app.router.add_get("/", home)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/start", api_start)
    app.router.add_post("/api/stop", api_stop)
    app.router.add_post("/api/config", api_config)
    app.router.add_get("/api/logs", api_logs)
    app.router.add_get("/api/test-engine", api_test_engine)
    app.router.add_get("/api/jobs", api_jobs)

    return app
