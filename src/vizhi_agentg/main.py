from __future__ import annotations

from aiohttp import web

from .dashboard.app import build_dashboard_app


def main() -> None:
    app = build_dashboard_app()
    web.run_app(app, host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()
