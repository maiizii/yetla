"""Pydantic schema 定义。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SubdomainRedirect(BaseModel):
    host: str = Field(..., description="例如 api.yet.la")
    target_url: str = Field(..., description="完整跳转地址")
    code: int = Field(default=302, description="HTTP 状态码")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class ShortLink(BaseModel):
    code: str = Field(..., description="短链编码")
    target_url: str = Field(..., description="目标地址")
    hits: int = Field(default=0, description="访问次数")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}

