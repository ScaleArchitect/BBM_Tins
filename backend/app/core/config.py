"""Application configuration (12-factor, env-driven).

Defaults mirror ``backend/.env.example`` so the app and tests boot without an
``.env`` file. Provider selection (storage/ocr/email/queue) is driven entirely
by environment so the same image runs locally and on Azure (see IA-02/05/07/08/09).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- general ---
    app_env: str = "local"

    # --- data stores ---
    # App connection: in Docker this is overridden to the non-superuser RLS-enforced
    # role (tin_app). The owner/admin connection below is used by migrations and the
    # platform cross-tenant path (bypasses RLS by design — Sprint 2+).
    database_url: str = "postgresql+asyncpg://tin:tin@db:5432/tin"
    database_admin_url: str | None = None
    redis_url: str = "redis://redis:6379/0"

    # --- provider selection ---
    storage_provider: str = "minio"  # local | minio | azure_blob
    ocr_provider: str = "local"  # local | azure
    email_provider: str = "smtp"  # smtp | acs | sendgrid
    queue_provider: str = "arq_redis"  # arq_redis | service_bus

    # --- storage (local/minio) ---
    minio_endpoint: str = "http://storage:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    storage_bucket: str = "tin-certs"

    # --- email (smtp) ---
    smtp_host: str = "mail"
    smtp_port: int = 1025
    email_from: str = "TIN Portal <no-reply@tinportal.local>"

    # --- security / auth ---
    # RS256 with keys from Key Vault in prod. Locally, if the PEM files are
    # absent, an ephemeral keypair is generated at startup (see core/security).
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: str = "/run/secrets/jwt_private.pem"
    jwt_public_key_path: str = "/run/secrets/jwt_public.pem"
    jwt_issuer: str = "tin-portal"
    jwt_access_ttl_seconds: int = 900  # 15 min
    jwt_refresh_ttl_seconds: int = 604800  # 7 days
    otp_pepper: str = "change-me-32-bytes"
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 3
    otp_lockout_seconds: int = 1800

    # TTL for a pending TOTP secret held server-side between enroll and verify.
    totp_pending_ttl_seconds: int = 600

    # --- admin login throttling (docs/architecture/02 §8.6) ---
    login_max_attempts: int = 5
    login_attempt_window_seconds: int = 900  # rolling window for counting failures
    login_lockout_seconds: int = 900  # cooldown once the cap is hit

    # --- refresh-token endpoint rate limit (per client IP, defence in depth) ---
    refresh_max_per_window: int = 60
    refresh_window_seconds: int = 60

    # --- public base URL (invitation / set-password links) ---
    public_base_url: str = "http://localhost"

    # --- dev bootstrap: first platform admin (seeded by `python -m app.seed`) ---
    platform_bootstrap_email: str = "platform@tinportal.local"
    platform_bootstrap_password: str = "ChangeMe!Platform1"

    # --- uploads ---
    max_upload_mb: int = 10
    signed_url_ttl: int = 300

    # --- domain policy defaults (configurable per IA-13/14/15/17) ---
    group_cert_policy: str = "REJECT"  # REJECT | WARN
    tin_derivation_mode: str = "TRN_FIRST_10"
    retention_months_default: int = 24

    # --- web ---
    cors_origins: list[str] = ["http://localhost", "http://localhost:3000"]
    api_v1_prefix: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
