"""Arq worker entrypoint (Sprint 0 placeholder).

Run with: ``arq app.worker.WorkerSettings``. Uses the SAME image as the API
(IA-06). Real tasks (ocr_extract, send_email, generate_export, purge_retention)
are registered in later sprints (docs/architecture/06 §13.6).
"""

from __future__ import annotations

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


async def ping(ctx: dict) -> str:  # noqa: ARG001
    """Trivial task proving the worker can process jobs."""
    get_logger("worker").info("ping")
    return "pong"


async def startup(ctx: dict) -> None:  # noqa: ARG001
    configure_logging()
    get_logger("worker").info("worker.startup")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [ping]
    on_startup = startup
