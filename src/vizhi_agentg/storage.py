from __future__ import annotations

import json
from pathlib import Path

from .models import AgentConfig


class FileStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / ".vizhi-agentg"
        self.root.mkdir(parents=True, exist_ok=True)
        self.config_path = self.root / "config.json"

    def load_config(self) -> AgentConfig:
        if not self.config_path.exists():
            return AgentConfig()
        raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        return AgentConfig.model_validate(raw)

    def save_config(self, config: AgentConfig) -> None:
        self.config_path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
