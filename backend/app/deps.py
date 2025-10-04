"""Shared dependencies for FastAPI routes."""
from __future__ import annotations

from typing import Generator, Literal
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SessionLocal, User
from .security import needs_rehash, rehash_password, verify_password
from .session import get_session, set_session

security = HTTPBasic(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a SQLAlchemy session for request lifecycle."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _authenticate(
    db: Session, username: str, password: str
) -> tuple[bool, Literal["username", "password", None], User | None]:
    """Validate credential pairs and return status plus failure reason."""

    normalized_username = (username or "").strip().lower()
    if not normalized_username:
        return False, "username", None

    user = db.scalar(select(User).where(User.username == normalized_username))
    if user is None:
        return False, "username", None

    if not verify_password(password or "", user.password_hash):
        return False, "password", None

    if needs_rehash(user.password_hash):
        user.password_hash = rehash_password(password or "", user.password_hash)
        db.add(user)
        db.commit()

    return True, None, user


def _session_user(request: Request, db: Session) -> User | None:
    session = get_session(request)
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None:
        return None
    return user


def require_authenticated_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> User:
    """Resolve the current authenticated user or raise if unauthenticated."""

    user = _session_user(request, db)
    if user is not None:
        return user

    accept_header = (request.headers.get("accept") or "").lower()
    expects_html = "text/html" in accept_header

    if credentials is not None and (not request.url.path.startswith("/admin") or not expects_html):
        ok, _, basic_user = _authenticate(db, credentials.username, credentials.password)
        if ok and basic_user is not None:
            return basic_user
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Basic"},
        )

    if expects_html or request.url.path.startswith("/admin"):
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


def require_admin_user(current_user: User = Depends(require_authenticated_user)) -> User:
    """Ensure the current user has administrator privileges."""

    if not current_user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def validate_credentials(
    username: str, password: str, db: Session
) -> tuple[bool, Literal["username", "password", None], User | None]:
    """Expose credential validation for the login flow."""

    return _authenticate(db, username, password)


def establish_session(response, request: Request, user: User) -> None:
    """Persist user identity into the signed session cookie."""

    set_session(
        response,
        request,
        {
            "is_authenticated": True,
            "user_id": user.id,
            "username": user.username,
            "is_admin": user.is_admin,
        },
    )
