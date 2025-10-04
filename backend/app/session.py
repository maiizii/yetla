"""Lightweight signed-cookie session helpers for the admin interface."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from typing import Any

from fastapi import Request, Response

SESSION_COOKIE_NAME = "yetla_session"
_SESSION_SECRET = os.getenv("SESSION_SECRET", os.getenv("ADMIN_PASS", "yetla-session")).encode("utf-8")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload: bytes) -> bytes:
    return hmac.new(_SESSION_SECRET, payload, hashlib.sha256).digest()


def serialize_session(data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = _sign(payload)
    return f"{_b64encode(payload)}.{_b64encode(signature)}"


def deserialize_session(token: str | None) -> dict[str, Any]:
    if not token:
        return {}
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
    except (ValueError, binascii.Error):
        return {}
    expected_signature = _sign(payload)
    if not hmac.compare_digest(signature, expected_signature):
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def get_session(request: Request) -> dict[str, Any]:
    cached = getattr(request.state, "_yetla_session", None)
    if cached is not None:
        return cached
    session = deserialize_session(request.cookies.get(SESSION_COOKIE_NAME))
    request.state._yetla_session = session
    return session


def set_session(response: Response, request: Request, data: dict[str, Any]) -> None:
    request.state._yetla_session = data
    response.set_cookie(
        SESSION_COOKIE_NAME,
        serialize_session(data),
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session(response: Response, request: Request) -> None:
    request.state._yetla_session = {}
    response.set_cookie(
        SESSION_COOKIE_NAME,
        "",
        path="/",
        max_age=0,
        expires=0,
        httponly=True,
        samesite="lax",
    )
