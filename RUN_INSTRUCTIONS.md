# Vizhi AgentG - Run Instructions

## Overview
The `vizhi-agentG` agent has been **fully refactored** with:
- **Static HTML/CSS/JS frontend** (instead of Python-generated HTML)
- **Clean JSON REST APIs** for all operations
- **Service layer** for better state management
- **Isolated engine testing** that doesn't interfere with runtime tasks
- **Better startup logging** and error handling

All UI/UX and functionality remain **exactly the same** — only the internal structure improved.

---

## Installation & Setup

### 1. Navigate to the project directory
```bash
cd /home/harish-25387/Documents/VizhiProd/vizhi-agentG
```

### 2. Create and activate virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the package in editable mode
```bash
pip install -e .
```

---

## Running the Agent

### Start the dashboard
```bash
vizhi-agentg
```

You should see:
```
🚀 Vizhi AgentG Dashboard
   → Dashboard: http://127.0.0.1:8080
   → Press Ctrl+C to stop
```

If port `8080` is already in use, it will automatically fall back to an available port.

### Open the dashboard in your browser
```
http://127.0.0.1:8080
```

---

## Using the Dashboard

### Configuration
1. Fill in your **Agent CID** and **API Key** (get these from the Vizhi cloud backend)
2. Select your **Engine** (Ollama or LM Studio)
3. Enter the **Model** name for that engine
4. Click **Save Configuration**

### Testing the Engine
- Click **Test Engine** to verify connectivity to your local LLM server
- This now runs in **isolation** without runtime interference
- Check the **Engine Logs** card for test results

### Starting the Agent
- Click **Start Agent** to begin processing cloud jobs
- The agent will:
  - Register with the cloud backend
  - Start websocket and polling loops
  - Process incoming inference jobs
  - Report back results

### Monitoring
- **Status Bar**: Shows connection status, active engine, uptime
- **Metrics**: Completed, failed, and queued job counts
- **Engine Logs**: Real-time engine activity
- **Job History**: Recent job execution records

---

## Architecture Changes

### What Changed

#### Before (Old Structure)
- Inline Python HTML generation in `dashboard/app.py`
- 500+ line f-string template
- Config/runtime state could drift
- Engine test used runtime state (caused failures)

#### After (New Structure)
```
src/vizhi_agentg/
├── dashboard/
│   ├── static/
│   │   ├── index.html      # Static UI markup
│   │   ├── app.css         # Styles
│   │   └── app.js          # Client-side logic
│   ├── app.py              # OLD (kept for reference)
│   └── app_new.py          # NEW clean backend
├── service.py              # NEW service layer
├── main.py                 # Updated to use app_new
└── ...
```

**Key improvements:**
- Frontend is now **plain HTML/CSS/JS** served as static assets
- Backend exposes **clean JSON APIs** only
- `AgentService` layer manages config/runtime/testing centrally
- Engine testing uses **isolated provider instances**
- No more state drift between config and runtime

### What Stayed the Same
- Same UI layout and design
- Same buttons and actions
- Same API endpoints (`/api/config`, `/api/test-engine`, etc.)
- Same config storage (SQLite in `~/.vizhi-agentg/`)
- Same job processing pipeline

---

## Troubleshooting

### Port already in use
If you see:
```
Dashboard port 8080 is already in use on 127.0.0.1.
Starting Vizhi AgentG on fallback port 42543 instead.
```

The agent automatically picks an available port. Use the printed URL.

### Engine test fails
1. Verify your LLM server is running:
   - **Ollama**: `http://127.0.0.1:11434`
   - **LM Studio**: `http://127.0.0.1:1234`
2. Check the **Engine Logs** for detailed error messages
3. Ensure the model name matches your loaded model

### Dashboard doesn't load
- Ensure you're using the **new** refactored code (main.py imports `app_new.py`)
- Check the console for any startup errors
- Verify static files exist in `src/vizhi_agentg/dashboard/static/`

### Static files not found after install
If you installed with `pip install .` (non-editable), verify `pyproject.toml` has:
```toml
[tool.setuptools.package-data]
vizhi_agentg = ["dashboard/static/*"]
```

Then reinstall: `pip install -e .`

---

## Development

### Running from source (recommended)
```bash
cd /home/harish-25387/Documents/VizhiProd/vizhi-agentG
source .venv/bin/activate
vizhi-agentg
```

### Making frontend changes
Edit files in `src/vizhi_agentg/dashboard/static/`:
- `index.html` - page structure
- `app.css` - styling
- `app.js` - client logic

Refresh browser to see changes (no restart needed for static files).

### Making backend changes
Edit `src/vizhi_agentg/dashboard/app_new.py` or other Python files.
Restart `vizhi-agentg` to apply changes.

---

## Next Steps

1. **Stop any old vizhi-agentg instances**:
   ```bash
   pkill -f vizhi-agentg
   ```

2. **Start the refactored agent**:
   ```bash
   cd /home/harish-25387/Documents/VizhiProd/vizhi-agentG
   source .venv/bin/activate
   vizhi-agentg
   ```

3. **Open the dashboard** in your browser

4. **Configure and test** your engine

5. **Start the agent** to begin processing jobs

---

## Summary

The refactored `vizhi-agentG` is now:
- ✅ Cleaner and easier to maintain
- ✅ More reliable (isolated engine testing)
- ✅ Better structured (service layer, static frontend)
- ✅ Same UX and functionality
- ✅ Ready for production use

Enjoy your improved Vizhi AgentG! 🚀
