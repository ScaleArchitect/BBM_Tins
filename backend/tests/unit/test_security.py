"""Unit tests for auth primitives: Argon2, RS256 JWT, token hashing (no DB)."""

from __future__ import annotations

import datetime as dt
import uuid

import jwt
import pytest

from app.core import security as s


def test_password_hash_roundtrip() -> None:
    hashed = s.hash_password("hunter2")
    assert hashed != "hunter2"
    assert s.verify_password("hunter2", hashed)
    assert not s.verify_password("wrong", hashed)


def test_verify_password_handles_garbage_hash() -> None:
    assert not s.verify_password("x", "not-a-valid-argon2-hash")


def test_access_token_roundtrip_carries_claims() -> None:
    pid, cid = uuid.uuid4(), uuid.uuid4()
    token, exp = s.create_access_token(
        principal_type=s.COMPANY, principal_id=pid, role="COMPANY_OWNER", company_id=cid
    )
    claims = s.decode_access_token(token)
    assert claims["sub"] == str(pid)
    assert claims["company_id"] == str(cid)
    assert claims["role"] == "COMPANY_OWNER"
    assert claims["typ"] == "access"
    assert exp > dt.datetime.now(dt.UTC)


def test_platform_token_has_null_company() -> None:
    token, _ = s.create_access_token(
        principal_type=s.PLATFORM, principal_id=uuid.uuid4(), role="PLATFORM_OWNER"
    )
    assert s.decode_access_token(token)["company_id"] is None


def test_decode_rejects_tampered_token() -> None:
    token, _ = s.create_access_token(
        principal_type=s.PLATFORM, principal_id=uuid.uuid4(), role="PLATFORM_OWNER"
    )
    with pytest.raises(jwt.PyJWTError):
        s.decode_access_token(token + "x")


def test_token_hash_is_stable_and_opaque() -> None:
    assert s.hash_token("abc") == s.hash_token("abc")
    assert s.hash_token("abc") != "abc"
    assert len(s.hash_token("abc")) == 64


def test_hash_otp_peppered() -> None:
    assert s.hash_otp("123456", "pepper") == s.hash_otp("123456", "pepper")
    assert s.hash_otp("123456", "pepper") != s.hash_otp("123456", "other")


def test_normalize_email() -> None:
    assert s.normalize_email("  Admin@ACME.AE ") == "admin@acme.ae"
