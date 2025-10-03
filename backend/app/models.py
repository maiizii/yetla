"""数据库模型与引擎配置。"""
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/data.db")


class Base(DeclarativeBase):
    """SQLAlchemy Declarative 基类。"""


engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


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

