"""Worker entry point for DevMind background task processing."""

import asyncio
import logging
import signal
from typing import Any

from app.core.logging import setup_logging
from app.core.settings import get_settings

logger = logging.getLogger("devmind.worker")


async def main() -> None:
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info("DevMind worker service started (mode=%s, env=%s)", settings.run_mode, settings.env)

    stop_event = asyncio.Event()

    def _signal_handler(*_: Any) -> None:
        logger.info("DevMind worker shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    logger.info("DevMind worker stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
