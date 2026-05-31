"""Azure Blob Storage provider (Sprint 0 stub).

Implemented for Azure deployment (Sprint 12). Uses managed identity +
user-delegation SAS for short-lived signed URLs. No Azure SDK import in Sprint 0.
"""

from __future__ import annotations

from app.providers.storage.base import StoredObject


class AzureBlobStorageProvider:
    def __init__(self, account: str, container: str) -> None:
        self.account = account
        self.container = container

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        raise NotImplementedError("AzureBlobStorageProvider — implemented in Sprint 12.")

    async def get(self, key: str) -> bytes:
        raise NotImplementedError

    async def signed_url(
        self, key: str, expires_s: int = 300, disposition: str | None = None
    ) -> str:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError
