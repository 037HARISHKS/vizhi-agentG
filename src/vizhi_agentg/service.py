"""Service layer for managing agent configuration, runtime, and engine testing."""

from __future__ import annotations

from typing import Any

from .models import AgentConfig
from .providers import build_provider
from .storage import SQLiteStore
from .worker import AgentRuntime


class AgentService:
    """Centralized service for agent operations."""

    def __init__(self) -> None:
        self.store = SQLiteStore()
        self.config = self.store.load_config()
        self.runtime = AgentRuntime(self.config)

    def get_config(self) -> AgentConfig:
        """Load and return current configuration."""
        self.config = self.store.load_config()
        return self.config

    def save_config(self, new_config: AgentConfig) -> None:
        """Save new configuration and update runtime."""
        self.store.save_config(new_config)
        self.config = new_config
        self.runtime.update_config(new_config)

    async def test_engine_isolated(self, engine_name: str | None = None) -> dict[str, Any]:
        """Test an engine in isolation without interference from runtime tasks.
        
        This creates a fresh provider instance and tests it directly,
        avoiding any potential state conflicts with background agent tasks.
        """
        # Always use fresh config
        cfg = self.store.load_config()
        
        # Resolve engine
        target_engine_name = (engine_name or cfg.default_engine).strip()
        engine = None
        
        for e in cfg.engines:
            if e.enabled and e.name.lower().replace(" ", "_") == target_engine_name.lower().replace(" ", "_"):
                engine = e
                break
        
        if not engine:
            # Fallback to first enabled engine
            for e in cfg.engines:
                if e.enabled:
                    engine = e
                    break
        
        if not engine:
            raise ValueError("No enabled engines configured")
        
        # Build provider directly
        provider_type = engine.provider_type.value if hasattr(engine.provider_type, "value") else str(engine.provider_type)
        provider = build_provider(provider_type, engine.endpoint, engine.model)
        
        # Test health check
        try:
            result = await provider.health_check()
            self.store.add_log(f"{engine.name}: health check passed")
            return result
        except Exception as exc:
            self.store.add_log(f"{engine.name}: health check failed - {exc}")
            raise

    def get_runtime(self) -> AgentRuntime:
        """Get the current runtime instance."""
        return self.runtime
