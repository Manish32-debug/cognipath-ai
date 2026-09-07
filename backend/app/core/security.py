"""Authentication primitives.

Scope statement: this is an academic prototype. It does the structurally correct
things - salted PBKDF2-HMAC-SHA256 password hashing (never plaintext), signed
JWTs with an expiry, and role checks enforced server side on every protected
route. It deliberately does NOT claim production readiness: there is no refresh
token rotation, no account lockout, no rate limiting, and the default signing
secret is a development placeholder that must be overridden via
COGNIPATH_SECRET.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    digest, _ = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest, password_hash)


def create_access_token(subject: str, role: str, student_id: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "student_id": student_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
