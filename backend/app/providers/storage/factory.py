"""Storage provider factory — selects implementation from settings (IA-07)."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.storage.base import StorageProvider


def build_storage_provider(settings: Settings) -> StorageProvider:
    provider = settings.storage_provider.lower()
    if provider == "local":
        from app.providers.storage.local_fs import LocalFsStorageProvider

        return LocalFsStorageProvider()
    if provider == "minio":
        from app.providers.storage.minio import MinioStorageProvider

        return MinioStorageProvider(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.storage_bucket,
        )
    if provider == "azure_blob":
        from app.providers.storage.azure_blob import AzureBlobStorageProvider

        return AzureBlobStorageProvider(account="", container=settings.storage_bucket)
    raise ValueError(f"Unknown STORAGE_PROVIDER: {settings.storage_provider!r}")
