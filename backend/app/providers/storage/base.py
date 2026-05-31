"""StorageProvider interface (docs/architecture/01 §7.6, IA-06).

PDFs live in object storage only — never the database. Access is via short-lived
signed URLs brokered by the API after an authz check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class StoredObject:
    key: str
    size_bytes: int
    content_type: str


class StorageProvider(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...

    async def get(self, key: str) -> bytes: ...

    async def signed_url(
        self, key: str, expires_s: int = 300, disposition: str | None = None
    ) -> str: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...
