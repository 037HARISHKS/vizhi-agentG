from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    ollama = "ollama"
    lm_studio = "lm_studio"
    openai_compatible = "openai_compatible"


class JobStatus(str, Enum):
    queued = "queued"
    accepted = "accepted"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class EngineConfig(BaseModel):
    name: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    provider_type: ProviderType = ProviderType.lm_studio
    model: str = ""
    enabled: bool = True


class AgentConfig(BaseModel):
    agent_id: str = "agent-local"
    agent_api_key: str = ""
    device_name: str = ""
    backend_url: str = "http://127.0.0.1:8000"
    ws_path: str = "/ws/agent"
    jobs_path: str = "/jobs/next"
    register_path: str = "/agents/register"
    heartbeat_path: str = "/agents/heartbeat"
    submit_path: str = "/jobs/submit"
    poll_interval_idle: int = 7
    poll_interval_busy: int = 3
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8080
    enable_websocket: bool = True
    enable_polling: bool = True
    default_engine: str = "ollama"
    engines: list[EngineConfig] = Field(
        default_factory=lambda: [
            EngineConfig(
                name="Ollama",
                endpoint="http://127.0.0.1:11434",
                provider_type=ProviderType.ollama,
            ),
            EngineConfig(
                name="LM Studio",
                endpoint="http://127.0.0.1:1234",
                provider_type=ProviderType.openai_compatible,
            ),
        ]
    )


class JobRequest(BaseModel):
    id: str
    model: str = ""
    engine: str = ""
    kind: str = "chat"
    input: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    output: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    completed_at: str = ""


class StatusSnapshot(BaseModel):
    agent_id: str
    device_name: str
    backend_url: str
    connected: bool
    websocket_connected: bool
    last_heartbeat: str = ""
    active_engine: str = ""
    active_job_id: str = ""
    queue_depth: int = 0
    total_completed: int = 0
    total_failed: int = 0
    uptime_seconds: int = 0
    available_engines: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)


@dataclass
class AgentRuntimeState:
    connected: bool = False
    websocket_connected: bool = False
    last_heartbeat: str = ""
    active_engine: str = ""
    active_job_id: str = ""
    queue_depth: int = 0
    total_completed: int = 0
    total_failed: int = 0
    logs: list[str] = field(default_factory=list)
    job_history: list[dict[str, Any]] = field(default_factory=list)
