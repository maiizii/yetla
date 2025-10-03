"""Shared dependencies for FastAPI routes."""
from __future__ import annotations

import os
import secrets
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from .models import SessionLocal

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")

security = HTTPBasic()


def get_db() -> Generator[Session, None, None]:
    """Provide a SQLAlchemy session for request lifecycle."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_basic_auth(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    """Enforce HTTP Basic authentication using environment credentials."""

    username = credentials.username or ""
    password = credentials.password or ""

    correct_username = secrets.compare_digest(username, ADMIN_USER or "")
    correct_password = secrets.compare_digest(password, ADMIN_PASS or "")

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Basic"},
        )
