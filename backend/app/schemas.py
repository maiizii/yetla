"""Pydantic schema 定义。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ValidationInfo, field_validator


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
    hits: int = Field(default=0, description="累计访问次数")
    user_id: int | None = Field(default=None, description="所属用户 ID")
    owner_username: str | None = Field(default=None, description="所属用户名")

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
    user_id: int | None = Field(default=None, description="所属用户 ID")
    owner_username: str | None = Field(default=None, description="所属用户名")

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


class UserBase(BaseModel):
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("用户名不能为空")
        return normalized

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("邮箱不能为空")
        return normalized


class UserCreate(UserBase):
    password: str = Field(..., description="登录密码")
    is_admin: bool = Field(default=False, description="是否管理员")

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("密码长度至少为 6 位")
        return value


class UserUpdate(UserBase):
    is_admin: bool = Field(default=False, description="是否管理员")
    password: str | None = Field(default=None, description="新密码，可选")

    @field_validator("password")
    @classmethod
    def _normalize_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) < 6:
            raise ValueError("密码长度至少为 6 位")
        return value


class User(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    current_password: str = Field(..., description="原密码")
    new_password: str = Field(..., description="新密码")
    confirm_password: str = Field(..., description="确认新密码")

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("密码长度至少为 6 位")
        return value

    @field_validator("confirm_password")
    @classmethod
    def _validate_confirm(cls, value: str, info: ValidationInfo) -> str:
        new_password = info.data.get("new_password") if info.data else None
        if new_password is not None and value != new_password:
            raise ValueError("两次输入的密码不一致")
        return value

