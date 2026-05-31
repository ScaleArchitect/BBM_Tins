"""Arq/Redis task queue (Sprint 0 stub).

Implemented in Sprint 5 when the first real job (OCR) is enqueued. Will use a
pooled arq RedisSettings connection.
"""

from __future__ import annotations


class ArqRedisTaskQueue:
    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url

    async def enqueue(self, task_name: str, *args: object, **kwargs: object) -> str:
        raise NotImplementedError("ArqRedisTaskQueue — implemented in Sprint 5.")
