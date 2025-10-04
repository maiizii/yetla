"""Shared dependencies for FastAPI routes."""
from __future__ import annotations

import os
import secrets
from typing import Generator
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from .models import SessionLocal
from .session import get_session

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")

security = HTTPBasic(auto_error=False)


def _authenticate(username: str, password: str) -> tuple[bool, str | None]:
    """Validate credential pairs and return status plus failure reason."""

    safe_username = username or ""
    safe_password = password or ""

    if not secrets.compare_digest(safe_username, ADMIN_USER or ""):
        return False, "username"
    if not secrets.compare_digest(safe_password, ADMIN_PASS or ""):
        return False, "password"
    return True, None


def get_db() -> Generator[Session, None, None]:
    """Provide a SQLAlchemy session for request lifecycle."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_basic_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    """Enforce HTTP Basic authentication using environment credentials."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Basic"},
        )

    ok, _ = _authenticate(credentials.username, credentials.password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Basic"},
        )


def require_admin_auth(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> None:
    """Allow either session-based login or HTTP Basic credentials."""

    session = get_session(request)
    if session.get("is_authenticated"):
        return

    accept_header = (request.headers.get("accept") or "").lower()
    accepts_html = "text/html" in accept_header

    if credentials is not None and (
        not request.url.path.startswith("/admin") or not accepts_html
    ):
        require_basic_auth(credentials)
        return

    if accepts_html or request.url.path.startswith("/admin"):
        target = request.url.path
        if request.url.query:
            target = f"{target}?{request.url.query}"
        redirect = "/admin/login"
        if target and target != "/admin/login":
            redirect = f"/admin/login?next={quote(target, safe='')}"
        raise HTTPException(
            status.HTTP_303_SEE_OTHER,
            detail="未登录",
            headers={"Location": redirect},
        )

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="未登录",
        headers={"WWW-Authenticate": "Basic"},
    )


def validate_credentials(username: str, password: str) -> tuple[bool, str | None]:
    """Expose credential validation for the login flow."""

    return _authenticate(username, password)
