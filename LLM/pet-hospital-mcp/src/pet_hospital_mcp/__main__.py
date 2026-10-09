"""Entry point: `python -m pet_hospital_mcp` or the `pet-hospital-mcp` script.

Serves the stateless Streamable HTTP app via uvicorn.
"""

from __future__ import annotations

import uvicorn

from pet_hospital_mcp.config import Config
from pet_hospital_mcp.logging_config import configure_logging
from pet_hospital_mcp.server import create_app


def main() -> None:
    cfg = Config.from_env()
    configure_logging()
    app = create_app(config=cfg)
    uvicorn.run(
        app,
        host=cfg.host,
        port=cfg.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
