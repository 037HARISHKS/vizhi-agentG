from __future__ import annotations

import uvicorn

from .dashboard.app import build_dashboard_app


app = build_dashboard_app()


def main() -> None:
    uvicorn.run(
        "vizhi_agentg.main:app",
        host="127.0.0.1",
        port=8080,
        reload=False,
    )


if __name__ == "__main__":
    main()
