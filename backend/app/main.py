"""FastAPI 应用，提供 Nginx 子域映射的示例接口。"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .models import Base, engine

app = FastAPI(
    title="Yetla Subdomain Router API",
    description=(
        "演示如何在后端维护子域与上游服务的映射，并暴露给基础设施层（如"
        " Nginx 模板渲染或自动化脚本）。"
    ),
    version="0.1.0",
)


@app.on_event("startup")
def ensure_tables() -> None:
    """应用启动时自动创建数据库表。"""

    Base.metadata.create_all(bind=engine)


class Route(BaseModel):
    """子域映射的展示模型。"""

    subdomain: str = Field(..., description="子域名，省略主域部分，例如 api")
    upstream: str = Field(..., description="Nginx upstream 名称或目标地址")
    description: str | None = Field(None, description="用途说明，方便运维辨识")
    permanent: bool = Field(
        default=True,
        description="是否推荐使用 301 永久重定向；为 False 时多用于临时跳转",
    )


# 在实际系统中，这些数据应来自数据库。
ROUTES: dict[str, Route] = {
    "api": Route(
        subdomain="api",
        upstream="app_api",
        description="供客户端与第三方调用的 API 服务",
    ),
    "console": Route(
        subdomain="console",
        upstream="app_console",
        description="内部运营控制台",
        permanent=False,
    ),
}


def _get_route_or_404(subdomain: str) -> Route:
    try:
        return ROUTES[subdomain]
    except KeyError as exc:  # pragma: no cover - 极简示例不接入测试框架
        raise HTTPException(status_code=404, detail="未找到子域映射") from exc


@app.get("/routes", response_model=list[Route])
def list_routes() -> list[Route]:
    """返回所有静态配置的子域映射。"""

    return sorted(ROUTES.values(), key=lambda route: route.subdomain)


@app.get("/routes/{subdomain}", response_model=Route)
def get_route(subdomain: str) -> Route:
    """查询单个子域配置。"""

    return _get_route_or_404(subdomain)
