"""Task queue factory — selects implementation from settings (IA-05)."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.queue.base import TaskQueue


def build_task_queue(settings: Settings) -> TaskQueue:
    provider = settings.queue_provider.lower()
    if provider == "arq_redis":
        from app.providers.queue.arq_redis import ArqRedisTaskQueue

        return ArqRedisTaskQueue(redis_url=settings.redis_url)
    if provider == "service_bus":
        from app.providers.queue.azure_service_bus import AzureServiceBusTaskQueue

        return AzureServiceBusTaskQueue()
    raise ValueError(f"Unknown QUEUE_PROVIDER: {settings.queue_provider!r}")
