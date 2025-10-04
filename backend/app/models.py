"""数据库模型与引擎配置。"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
    inspect,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/data.db")


def _ensure_sqlite_directory(database_url: str) -> None:
    """Ensure the parent directory for a SQLite database exists."""

    url = make_url(database_url)
    if url.drivername != "sqlite":
        return

    database = url.database or ""
    if not database or database == ":memory:":
        return

    db_path = Path(database)
    parent = db_path.parent
    if parent.exists():
        return

    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - depends on environment permissions
        raise RuntimeError(
            f"无法创建 SQLite 数据目录: {parent!s}"
        ) from exc


_ensure_sqlite_directory(DATABASE_URL)


class Base(DeclarativeBase):
    """SQLAlchemy Declarative 基类。"""


engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class User(Base):
    """系统用户表，支持管理员与普通用户。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    short_links: Mapped[list["ShortLink"]] = relationship(back_populates="owner")
    subdomain_redirects: Mapped[list["SubdomainRedirect"]] = relationship(
        back_populates="owner"
    )


class SubdomainRedirect(Base):
    """子域名重定向规则。"""

    __tablename__ = "subdomain_redirects"

    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    code: Mapped[int] = mapped_column("code_int", Integer, default=302, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    hits: Mapped[int] = mapped_column("hits_int", Integer, default=0, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    owner: Mapped[User | None] = relationship(back_populates="subdomain_redirects")

    @property
    def owner_username(self) -> str | None:  # pragma: no cover - 简单访问器
        return self.owner.username if self.owner else None


class ShortLink(Base):
    """短链接记录表。"""

    __tablename__ = "short_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    hits: Mapped[int] = mapped_column("hits_int", Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    owner: Mapped[User | None] = relationship(back_populates="short_links")

    @property
    def owner_username(self) -> str | None:  # pragma: no cover - 简单访问器
        return self.owner.username if self.owner else None


def ensure_subdomain_hits_column() -> None:
    """Ensure the legacy databases have the hits column for subdomain redirects."""

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("subdomain_redirects")}
    if "hits_int" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE subdomain_redirects ADD COLUMN hits_int INTEGER NOT NULL DEFAULT 0")
        )


def ensure_user_association_columns() -> None:
    """Ensure legacy tables have user_id columns for ownership tracking."""

    inspector = inspect(engine)

    short_link_columns = {
        column["name"] for column in inspector.get_columns("short_links")
    }
    if "user_id" not in short_link_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE short_links ADD COLUMN user_id INTEGER REFERENCES users(id)")
            )

    subdomain_columns = {
        column["name"] for column in inspector.get_columns("subdomain_redirects")
    }
    if "user_id" not in subdomain_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE subdomain_redirects ADD COLUMN user_id INTEGER REFERENCES users(id)"
                )
            )

