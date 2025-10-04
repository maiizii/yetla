"""User management helpers for startup and CRUD operations."""
from __future__ import annotations

import os

from sqlalchemy import select

from .models import SessionLocal, User
from .security import hash_password, needs_rehash, verify_password

DEFAULT_ADMIN_USER = os.getenv("ADMIN_USER", "admin").strip().lower()
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "admin")
DEFAULT_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")


def ensure_default_admin() -> None:
    """Ensure the default admin user exists in the database."""

    if not DEFAULT_ADMIN_USER or not DEFAULT_ADMIN_PASSWORD:
        return

    with SessionLocal() as session:
        existing = session.scalar(
            select(User).where(User.username == DEFAULT_ADMIN_USER)
        )
        if existing is None:
            admin = User(
                username=DEFAULT_ADMIN_USER,
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                is_admin=True,
            )
            session.add(admin)
            session.commit()
            return

        updated = False
        if not existing.is_admin:
            existing.is_admin = True
            updated = True
        if not existing.email:
            existing.email = DEFAULT_ADMIN_EMAIL
            updated = True

        password_matches_default = verify_password(
            DEFAULT_ADMIN_PASSWORD, existing.password_hash
        )
        if password_matches_default and needs_rehash(existing.password_hash):
            existing.password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
            updated = True

        if updated:
            session.add(existing)
            session.commit()
