"""TaskQueue interface (docs/architecture/01 §7.4, IA-05).

Abstracts the async job broker so Redis/Arq (local) can be swapped for Azure
Service Bus without touching call sites. The API enqueues; workers consume.
"""

from __future__ import annotations

from typing import Protocol


class TaskQueue(Protocol):
    async def enqueue(self, task_name: str, *args: object, **kwargs: object) -> str:
        """Enqueue a job; returns a job id."""
        ...
