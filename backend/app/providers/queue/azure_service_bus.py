"""Azure Service Bus task queue (Sprint 0 stub). Implemented Sprint 12 if needed."""

from __future__ import annotations


class AzureServiceBusTaskQueue:
    def __init__(self, connection_string: str = "") -> None:
        self.connection_string = connection_string

    async def enqueue(self, task_name: str, *args: object, **kwargs: object) -> str:
        raise NotImplementedError("AzureServiceBusTaskQueue — implemented in Sprint 12.")
