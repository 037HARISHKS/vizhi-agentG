// Vizhi AgentG Dashboard - Client-side Application

// Toast notification
function toast(msg, ok) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = ok ? 'var(--accent)' : 'var(--danger)';
  t.style.color = ok ? '#071a12' : '#fff';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}

// Fetch JSON helper
async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

// Post JSON helper
async function postJson(url, body) {
  return fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
}

// Load initial state on page load
async function loadInitialState() {
  try {
    // Load config
    const config = await fetchJson('/api/config');
    populateConfig(config);
    
    // Load status
    await refreshStatus();
    
    // Load logs
    await refreshLogs();
    
    // Load jobs
    await refreshJobs();
  } catch (err) {
    console.error('Failed to load initial state:', err);
  }
}

// Populate config form
function populateConfig(config) {
  document.getElementById('cfg-agent-id').value = config.agent_id || '';
  document.getElementById('cfg-api-key').value = config.agent_api_key || '';
  document.getElementById('cfg-engine').value = config.default_engine || 'ollama';
  
  // Find the selected engine and populate model
  const engines = config.engines || [];
  const selectedEngine = engines.find(e => 
    e.name.toLowerCase().replace(' ', '_') === config.default_engine.toLowerCase().replace(' ', '_')
  );
  document.getElementById('cfg-model').value = selectedEngine?.model || '';
}

// Refresh status bar and metrics
async function refreshStatus() {
  try {
    const status = await fetchJson('/api/status');
    
    // Update status bar
    document.getElementById('val-agent').textContent = status.agent_id || '—';
    document.getElementById('val-conn').textContent = status.connected ? 'Yes' : 'No';
    document.getElementById('val-ws').textContent = status.websocket_connected ? 'Live' : 'Off';
    document.getElementById('val-engine').textContent = status.active_engine || 'idle';
    
    const upMins = Math.floor(status.uptime_seconds / 60);
    const upSecs = status.uptime_seconds % 60;
    document.getElementById('val-uptime').textContent = `${upMins}m ${upSecs}s`;
    
    // Update indicators
    const indAgent = document.getElementById('ind-agent');
    const indConn = document.getElementById('ind-conn');
    const indWs = document.getElementById('ind-ws');
    
    indAgent.classList.toggle('indicator-on', status.connected);
    indAgent.classList.toggle('indicator-off', !status.connected);
    indConn.classList.toggle('indicator-on', status.connected);
    indConn.classList.toggle('indicator-off', !status.connected);
    indWs.classList.toggle('indicator-on', status.websocket_connected);
    indWs.classList.toggle('indicator-off', !status.websocket_connected);
    
    // Update metrics
    document.getElementById('metric-completed').textContent = status.total_completed || 0;
    document.getElementById('metric-failed').textContent = status.total_failed || 0;
    document.getElementById('metric-queued').textContent = status.queue_depth || 0;
    
    // Update available engines
    const engines = status.available_engines || [];
    document.getElementById('available-engines').textContent = engines.length ? engines.join(', ') : 'None configured';
  } catch (err) {
    console.error('Failed to refresh status:', err);
  }
}

// Refresh logs
async function refreshLogs() {
  try {
    const data = await fetchJson('/api/logs');
    const box = document.getElementById('log-box');
    const logs = data.logs || [];
    
    if (logs.length) {
      box.innerHTML = logs.map(l =>
        `<div class="log-line"><span class="log-ts">${l.timestamp}</span>${l.message}</div>`
      ).join('');
    } else {
      box.innerHTML = '<div class="log-empty">No engine logs yet</div>';
    }
  } catch (err) {
    console.error('Failed to refresh logs:', err);
  }
}

// Refresh job history
async function refreshJobs() {
  try {
    const data = await fetchJson('/api/jobs');
    const tbody = document.getElementById('job-history-body');
    const jobs = data.jobs || [];
    
    if (jobs.length) {
      tbody.innerHTML = jobs.map(j => {
        const statusCls = j.status === 'completed' ? 'st-ok' : 'st-err';
        const jobIdShort = (j.job_id || '').substring(0, 16);
        const completed = j.completed_at ? j.completed_at.substring(0, 19) : '—';
        const error = j.error ? j.error.substring(0, 40) : '—';
        
        return `<tr>
          <td class="mono">${jobIdShort}</td>
          <td><span class="badge ${statusCls}">${j.status}</span></td>
          <td>${completed}</td>
          <td class="mono">${error}</td>
        </tr>`;
      }).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No jobs processed yet</td></tr>';
    }
  } catch (err) {
    console.error('Failed to refresh jobs:', err);
  }
}

// Config form submit handler
document.getElementById('cfg-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const fd = new FormData(e.target);
    await postJson('/api/config', Object.fromEntries(fd.entries()));
    toast('Configuration saved!', true);
    setTimeout(() => location.reload(), 800);
  } catch (err) {
    toast('Save failed: ' + err.message, false);
  }
});

// Control agent (start/stop)
async function controlAgent(action) {
  try {
    await postJson(`/api/${action}`);
    toast(`Agent ${action} successful`, true);
    setTimeout(() => location.reload(), 1000);
  } catch (err) {
    toast(`${action} failed: ${err.message}`, false);
  }
}

// Test engine
async function testEngine() {
  try {
    const res = await fetchJson('/api/test-engine');
    if (res.ok) {
      toast('Engine OK!', true);
    } else {
      toast('Engine error: ' + (res.error || 'unknown'), false);
    }
  } catch (err) {
    toast('Engine test failed: ' + err.message, false);
  }
}

// Auto-refresh every 10 seconds
setInterval(() => {
  refreshStatus();
  refreshLogs();
}, 10000);

// Load initial state on page load
loadInitialState();
