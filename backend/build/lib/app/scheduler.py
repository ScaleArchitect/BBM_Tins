"""Arq scheduler entrypoint (Sprint 0 placeholder).

Run with: ``arq app.scheduler.SchedulerSettings``. Cron jobs (daily reminders,
weekly summary, nightly retention purge, OTP cleanup) are added in later sprints
(docs/architecture/06 §13.6, 08 §15.4). For now it runs a heartbeat.
"""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


async def heartbeat(ctx: dict) -> None:  # noqa: ARG001
    get_logger("scheduler").info("scheduler.heartbeat")


async def startup(ctx: dict) -> None:  # noqa: ARG001
    configure_logging()
    get_logger("scheduler").info("scheduler.startup")


class SchedulerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = startup
    cron_jobs = [cron(heartbeat, second=0)]  # once a minute; replaced by real jobs later
