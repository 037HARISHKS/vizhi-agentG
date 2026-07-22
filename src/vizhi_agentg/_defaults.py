"""Internal defaults for Vizhi AgentG."""

from __future__ import annotations

import os

# The production Vizhi backend URL.
DEFAULT_BACKEND_URL = "https://gopinathv19-vizhi-backend.hf.space"


def resolve_backend_url() -> str:
    """Resolve backend URL from environment with a safe default.

    This keeps older imports working while allowing deployments to override
    the backend target through ``VIZHI_BACKEND_URL``.
    """

    return os.getenv("VIZHI_BACKEND_URL", DEFAULT_BACKEND_URL).strip() or DEFAULT_BACKEND_URL
