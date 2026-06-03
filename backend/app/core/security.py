"""Security primitives: Argon2id password hashing + RS256 JWT (docs/architecture/02 §8.1).

- Passwords: Argon2id via ``argon2-cffi`` (per-password salt, tuned params).
- JWT: RS256 (asymmetric). In production the keypair comes from Key Vault via the
  ``JWT_*_KEY_PATH`` files. Locally, if those files are absent, an **ephemeral**
  keypair is generated once per process (dev convenience) — access tokens are short
  lived and refresh tokens are DB-backed, so a restart simply forces re-login.
- OTP hashing (HMAC-SHA256 + pepper) lands in Sprint 4; the helper is provided here
  so the customer-auth module can import it.

The module also exposes the request-time principal extraction used by RBAC and the
tenant-session dependency.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

_log = get_logger("security")
_ph = PasswordHasher()  # argon2id with sane library defaults

# Principal types carried in the JWT `principal_type` claim.
PLATFORM = "PLATFORM"
COMPANY = "COMPANY"
CUSTOMER = "CUSTOMER"


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


# --------------------------------------------------------------------------- #
# Opaque-token + OTP hashing
# --------------------------------------------------------------------------- #
def hash_token(token: str) -> str:
    """SHA-256 of an opaque token (refresh tokens, invitation tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


def hash_otp(code: str, pepper: str) -> str:
    """HMAC-SHA256(code, pepper) — peppered OTP hashing (Sprint 4 customer auth)."""
    return hmac.new(pepper.encode(), code.encode(), hashlib.sha256).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


# --------------------------------------------------------------------------- #
# JWT keypair (file-backed in prod, ephemeral in dev)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _KeyPair:
    private_pem: str
    public_pem: str


@lru_cache
def _keypair() -> _KeyPair:
    settings = get_settings()
    priv_path, pub_path = Path(settings.jwt_private_key_path), Path(settings.jwt_public_key_path)
    if priv_path.is_file() and pub_path.is_file():
        return _KeyPair(priv_path.read_text(), pub_path.read_text())

    # No provisioned keys (local/dev). Reuse a stable per-machine dev keypair so
    # tokens survive process restarts; only generate a fresh one if it's missing.
    dev_dir = Path(tempfile.gettempdir()) / "tin-portal-dev-jwt"
    dev_priv, dev_pub = dev_dir / "private.pem", dev_dir / "public.pem"
    if dev_priv.is_file() and dev_pub.is_file():
        _log.info("jwt_dev_keypair_reused", detail=str(dev_dir))
        return _KeyPair(dev_priv.read_text(), dev_pub.read_text())

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    persisted = False
    try:
        dev_dir.mkdir(parents=True, exist_ok=True)
        dev_priv.write_text(private_pem)
        dev_pub.write_text(public_pem)
        try:  # best-effort tighten perms (POSIX only)
            dev_priv.chmod(0o600)
        except OSError:
            pass
        persisted = True
    except OSError:
        pass

    _log.warning(
        "jwt_dev_keypair_generated",
        detail=(
            "JWT key files not found; generated a dev keypair. "
            + (
                f"Persisted to {dev_dir} so tokens survive restarts. "
                if persisted
                else "Could not persist it; tokens will not survive a restart. "
            )
            + "Provision keys in production."
        ),
        private_key_path=str(priv_path),
    )
    return _KeyPair(private_pem, public_pem)


# --------------------------------------------------------------------------- #
# Access-token issuance / verification
# --------------------------------------------------------------------------- #
def create_access_token(
    *,
    principal_type: str,
    principal_id: UUID,
    role: str,
    company_id: UUID | None = None,
    settings: Settings | None = None,
) -> tuple[str, dt.datetime]:
    """Return ``(jwt, expiry)``. Claims follow docs/architecture/02 §8.1."""
    settings = settings or get_settings()
    now = dt.datetime.now(dt.UTC)
    exp = now + dt.timedelta(seconds=settings.jwt_access_ttl_seconds)
    claims = {
        "sub": str(principal_id),
        "principal_type": principal_type,
        "role": role,
        "company_id": str(company_id) if company_id else None,
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid4().hex,
        "typ": "access",
    }
    token = jwt.encode(claims, _keypair().private_pem, algorithm=settings.jwt_algorithm)
    return token, exp


def decode_access_token(token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return jwt.decode(
        token,
        _keypair().public_pem,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub"]},
    )


# --------------------------------------------------------------------------- #
# Request principal
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Principal:
    principal_type: str
    id: UUID
    role: str
    company_id: UUID | None

    @property
    def is_platform(self) -> bool:
        return self.principal_type == PLATFORM


def _principal_from_claims(claims: dict) -> Principal:
    cid = claims.get("company_id")
    return Principal(
        principal_type=claims["principal_type"],
        id=UUID(claims["sub"]),
        role=claims["role"],
        company_id=UUID(cid) if cid else None,
    )


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or malformed bearer token")
    return token


async def get_current_principal(request: Request) -> Principal:
    """Decode the bearer access token into a :class:`Principal` (401 on failure)."""
    token = _bearer_token(request)
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if claims.get("typ") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")
    return _principal_from_claims(claims)


def require_platform(principal: Principal = Depends(get_current_principal)) -> Principal:
    if not principal.is_platform:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator required")
    return principal
