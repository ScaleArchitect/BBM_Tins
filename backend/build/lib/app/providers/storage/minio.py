"""MinIO (S3-compatible) storage provider (Sprint 0 stub).

Implemented in Sprint 5. Will use tenant-prefixed keys and presigned URLs that
behave identically to Azure Blob SAS URLs.
"""

from __future__ import annotations

from app.providers.storage.base import StoredObject


class MinioStorageProvider:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        raise NotImplementedError("MinioStorageProvider — implemented in Sprint 5.")

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
