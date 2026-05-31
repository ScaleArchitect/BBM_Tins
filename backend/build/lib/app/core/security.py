"""Security primitives (placeholder for Sprint 0).

Full implementation lands in Sprint 2 (admin auth) and Sprint 4 (customer OTP):
- Argon2id password hashing (IA-09)
- RS256 JWT access/refresh with rotation (docs/architecture/02 §8.1)
- HMAC-SHA256(+pepper) OTP hashing (IA-10)

Signatures are defined now so dependent modules can reference them; they raise
until implemented to avoid shipping insecure stubs.
"""

from __future__ import annotations


def hash_password(plain: str) -> str:
    raise NotImplementedError("Argon2id hashing — implemented in Sprint 2 (IA-09).")


def verify_password(plain: str, hashed: str) -> bool:
    raise NotImplementedError("Argon2id verify — implemented in Sprint 2 (IA-09).")


def hash_otp(code: str, pepper: str) -> str:
    raise NotImplementedError("HMAC-SHA256 OTP hashing — implemented in Sprint 4 (IA-10).")


def create_access_token(claims: dict[str, object]) -> str:
    raise NotImplementedError("RS256 JWT issuance — implemented in Sprint 2.")
