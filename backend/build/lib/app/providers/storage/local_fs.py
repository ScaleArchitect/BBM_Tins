"""Local filesystem storage provider (Sprint 0 stub).

Minimal implementation deferred to Sprint 5 (upload). Interface only for now.
"""

from __future__ import annotations

from app.providers.storage.base import StoredObject


class LocalFsStorageProvider:
    def __init__(self, root: str = "/data/storage") -> None:
        self.root = root

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        raise NotImplementedError("LocalFsStorageProvider.put — implemented in Sprint 5.")

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
