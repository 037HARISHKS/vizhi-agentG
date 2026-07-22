from __future__ import annotations

import socket

from aiohttp import web

from .dashboard.app_new import build_dashboard_app
from .storage import SQLiteStore


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex((host, port)) != 0


def _resolve_dashboard_bind() -> tuple[str, int]:
    config = SQLiteStore().load_config()
    host = config.dashboard_host
    preferred_port = config.dashboard_port

    if _port_available(host, preferred_port):
        return host, preferred_port

    fallback_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        fallback_sock.bind((host, 0))
        _, fallback_port = fallback_sock.getsockname()
    finally:
        fallback_sock.close()

    print(
        f"Dashboard port {preferred_port} is already in use on {host}. "
        f"Starting Vizhi AgentG on fallback port {fallback_port} instead."
    )
    return host, int(fallback_port)


def main() -> None:
    """Start the Vizhi AgentG dashboard server."""
    app = build_dashboard_app()
    host, port = _resolve_dashboard_bind()
    
    print(f"\n🚀 Vizhi AgentG Dashboard")
    print(f"   → Dashboard: http://{host}:{port}")
    print(f"   → Press Ctrl+C to stop\n")
    
    web.run_app(app, host=host, port=port, print=lambda x: None)


if __name__ == "__main__":
    main()
