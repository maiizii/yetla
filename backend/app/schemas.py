"""Pydantic schema 定义。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SubdomainRedirectBase(BaseModel):
    host: str = Field(..., description="例如 api.yet.la")
    target_url: str = Field(..., description="完整跳转地址")
    code: int = Field(default=302, description="HTTP 状态码")

    @field_validator("host")
    @classmethod
    def _normalize_host(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: int) -> int:
        if value not in {301, 302}:
            raise ValueError("仅支持 301 或 302 重定向")
        return value


class SubdomainRedirect(SubdomainRedirectBase):
    id: int = Field(..., description="数据库主键")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class SubdomainRedirectCreate(SubdomainRedirectBase):
    pass


class SubdomainRedirectUpdate(SubdomainRedirectBase):
    pass


class ShortLinkBase(BaseModel):
    target_url: str = Field(..., description="目标地址")


class ShortLinkCreate(ShortLinkBase):
    code: str | None = Field(default=None, description="短链编码，可为空自动生成")

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ShortLink(ShortLinkBase):
    id: int = Field(..., description="数据库主键")
    code: str = Field(..., description="短链编码")
    hits: int = Field(default=0, description="访问次数")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class ShortLinkUpdate(ShortLinkBase):
    code: str = Field(..., description="短链编码")

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("短链编码不能为空")
        return stripped

