"""密码哈希与校验工具。"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

_HASH_ALGORITHM: Final = "sha256"
_DEFAULT_ITERATIONS: Final = 600_000


class PasswordFormatError(ValueError):
    """Raised when a stored password hash cannot be parsed."""


def _split_components(stored: str) -> tuple[str, int, bytes, bytes]:
    try:
        scheme, iterations_str, salt_hex, hash_hex = stored.split("$", 3)
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        hashed = bytes.fromhex(hash_hex)
    except ValueError as exc:  # pragma: no cover - defensive
        raise PasswordFormatError("invalid password hash format") from exc
    if scheme != "pbkdf2_sha256":  # pragma: no cover - defensive
        raise PasswordFormatError(f"unsupported hash scheme: {scheme}")
    return scheme, iterations, salt, hashed


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = _DEFAULT_ITERATIONS) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""

    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    salt_bytes = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        _HASH_ALGORITHM, password.encode("utf-8"), salt_bytes, iterations
    )
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        salt_bytes.hex(),
        derived.hex(),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against the stored hash."""

    try:
        _, iterations, salt, expected = _split_components(stored_hash)
    except PasswordFormatError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        _HASH_ALGORITHM, password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored_hash: str, *, iterations: int = _DEFAULT_ITERATIONS) -> bool:
    """Determine whether the stored hash should be upgraded."""

    try:
        _, stored_iterations, _, _ = _split_components(stored_hash)
    except PasswordFormatError:
        return True
    return stored_iterations < iterations


def rehash_password(password: str, stored_hash: str) -> str:
    """Rehash a password with the recommended iterations if needed."""

    if not needs_rehash(stored_hash):
        return stored_hash
    return hash_password(password)
