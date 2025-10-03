"""FastAPI 应用，提供 yet.la 的短链接与子域跳转管理接口。"""
from __future__ import annotations

import os
import secrets
import string

from typing import Any
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .deps import get_db, require_basic_auth
from .models import Base, ShortLink, SubdomainRedirect, engine
from .schemas import (
    ShortLink as ShortLinkSchema,
    ShortLinkCreate,
    SubdomainRedirect as SubdomainRedirectSchema,
    SubdomainRedirectCreate,
)
from pydantic import ValidationError

SHORT_CODE_LEN = int(os.getenv("SHORT_CODE_LEN", "6"))
MAX_CODE_ATTEMPTS = 10

app = FastAPI(
    title="Yetla Redirect API",
    description="管理短链接与子域跳转的受保护接口，并提供公共重定向入口。",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
)


from .views import router as admin_router  # noqa: E402  pylint: disable=wrong-import-position

app.include_router(admin_router, dependencies=[Depends(require_basic_auth)])


@app.on_event("startup")
def ensure_tables() -> None:
    """应用启动时自动创建数据库表。"""

    Base.metadata.create_all(bind=engine)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """为 404/409 返回统一结构，方便调用方解析。"""

    hx_request = request.headers.get("hx-request") == "true"
    if exc.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT}:
        if hx_request:
            return HTMLResponse(
                (
                    "<div class=\"rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700\">"
                    f"{exc.detail}"
                    "</div>"
                ),
                status_code=exc.status_code,
            )
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY and hx_request:
        return HTMLResponse(
            (
                "<div class=\"rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700\">"
                f"{_format_validation_errors(exc.detail)}"
                "</div>"
            ),
            status_code=exc.status_code,
        )
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers or {}
    )
def _generate_unique_code(db: Session, length: int) -> str:
    """生成唯一的短链接 code。"""

    alphabet = string.ascii_letters + string.digits
    for _ in range(MAX_CODE_ATTEMPTS):
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = db.scalar(select(ShortLink).where(ShortLink.code == candidate))
        if not exists:
            return candidate
    raise HTTPException(status.HTTP_409_CONFLICT, detail="无法生成唯一的短链接编码")


def _compose_redirect_target(base_url: str, path: str, query: str) -> str:
    """组合目标 URL，将当前请求的 path/query 透传给上游。"""

    destination = base_url.rstrip("/")
    normalized_path = path.lstrip("/")
    if normalized_path:
        destination = f"{destination}/{normalized_path}"
    if query:
        separator = "&" if "?" in destination else "?"
        destination = f"{destination}{separator}{query}"
    return destination


async def _parse_short_link_payload(request: Request) -> ShortLinkCreate:
    """解析短链请求载荷，兼容 JSON 与表单提交。"""

    content_type = request.headers.get("content-type", "").lower()
    data: dict[str, Any]
    if content_type.startswith("application/json"):
        data = await request.json()
    elif content_type.startswith("application/x-www-form-urlencoded"):
        body_bytes = await request.body()
        decoded = body_bytes.decode("utf-8") if body_bytes else ""
        data = dict(parse_qsl(decoded, keep_blank_values=True))
    else:
        form = await request.form()
        data = {key: value for key, value in form.multi_items()}

    try:
        return ShortLinkCreate.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - FastAPI 将统一处理
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


async def _parse_subdomain_payload(request: Request) -> SubdomainRedirectCreate:
    """解析子域跳转请求载荷，支持 JSON 与表单提交。"""

    content_type = request.headers.get("content-type", "").lower()
    data: dict[str, Any]
    if content_type.startswith("application/json"):
        data = await request.json()
    elif content_type.startswith("application/x-www-form-urlencoded"):
        body_bytes = await request.body()
        decoded = body_bytes.decode("utf-8") if body_bytes else ""
        data = dict(parse_qsl(decoded, keep_blank_values=True))
    else:
        form = await request.form()
        data = {key: value for key, value in form.multi_items()}

    try:
        return SubdomainRedirectCreate.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - FastAPI 将统一处理
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _format_validation_errors(detail: Any) -> str:
    """将 Pydantic 错误信息转换为可读字符串。"""

    if isinstance(detail, list):
        messages: list[str] = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            loc = item.get("loc", [])
            field = next(
                (
                    str(part)
                    for part in loc
                    if isinstance(part, str) and part not in {"body", "__root__"}
                ),
                "请求",
            )
            message = item.get("msg", "输入不合法")
            messages.append(f"{field}: {message}")
        if messages:
            return "；".join(messages)
    return str(detail)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    """健康检查端点。"""

    return {"ok": True}


@app.get("/routes", response_model=list[SubdomainRedirectSchema])
def list_routes(db: Session = Depends(get_db)) -> list[SubdomainRedirect]:
    """公共接口：返回全部子域跳转规则。"""

    redirects = db.scalars(select(SubdomainRedirect).order_by(SubdomainRedirect.host)).all()
    return list(redirects)


@app.get(
    "/api/links",
    response_model=list[ShortLinkSchema],
    dependencies=[Depends(require_basic_auth)],
)
def list_short_links(db: Session = Depends(get_db)) -> list[ShortLink]:
    """列出所有短链接。"""

    links = db.scalars(select(ShortLink).order_by(ShortLink.created_at.desc())).all()
    return list(links)


@app.post(
    "/api/links",
    response_model=ShortLinkSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_basic_auth)],
)
async def create_short_link(
    request: Request,
    payload: ShortLinkCreate = Depends(_parse_short_link_payload),
    db: Session = Depends(get_db),
) -> Response:
    """创建短链接，code 可空自动生成。"""

    code = payload.code
    if code:
        exists = db.scalar(select(ShortLink).where(ShortLink.code == code))
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="短链接编码已存在")
    else:
        code = _generate_unique_code(db, SHORT_CODE_LEN)

    short_link = ShortLink(code=code, target_url=payload.target_url)
    db.add(short_link)
    db.commit()
    db.refresh(short_link)
    hx_request = request.headers.get("hx-request") == "true"
    if hx_request:
        message = (
            "<div class=\"rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700\">"
            "短链创建成功：<code class=\"font-mono\">"
            f"{short_link.code}"
            "</code></div>"
        )
        return HTMLResponse(
            message,
            status_code=status.HTTP_201_CREATED,
            headers={"HX-Trigger": "refresh-links"},
        )
    body = ShortLinkSchema.model_validate(short_link).model_dump(mode="json")
    return JSONResponse(
        body,
        status_code=status.HTTP_201_CREATED,
        headers={"HX-Trigger": "refresh-links"},
    )


@app.delete(
    "/api/links/{link_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_basic_auth)],
)
def delete_short_link(
    link_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    """删除指定短链接。"""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")
    db.delete(short_link)
    db.commit()
    hx_request = request.headers.get("hx-request") == "true"
    if hx_request:
        message = (
            "<div class=\"rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700\">"
            "短链已删除"
            "</div>"
        )
        return HTMLResponse(
            message,
            status_code=status.HTTP_200_OK,
            headers={"HX-Trigger": "refresh-links"},
        )
    response.headers["HX-Trigger"] = "refresh-links"
    return Response(status_code=status.HTTP_200_OK)


@app.get(
    "/api/subdomains",
    response_model=list[SubdomainRedirectSchema],
    dependencies=[Depends(require_basic_auth)],
)
def list_subdomains(db: Session = Depends(get_db)) -> list[SubdomainRedirect]:
    """列出所有子域跳转规则。"""

    redirects = db.scalars(
        select(SubdomainRedirect).order_by(SubdomainRedirect.created_at.desc())
    ).all()
    return list(redirects)


@app.post(
    "/api/subdomains",
    response_model=SubdomainRedirectSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_basic_auth)],
)
async def create_subdomain(
    request: Request,
    payload: SubdomainRedirectCreate = Depends(_parse_subdomain_payload),
    db: Session = Depends(get_db),
) -> Response:
    """创建子域跳转规则，Host 为完整域名。"""

    host = payload.host
    existing = db.scalar(select(SubdomainRedirect).where(SubdomainRedirect.host == host))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="子域跳转已存在")

    redirect = SubdomainRedirect(host=host, target_url=payload.target_url, code=payload.code)
    db.add(redirect)
    db.commit()
    db.refresh(redirect)

    hx_request = request.headers.get("hx-request") == "true"
    if hx_request:
        message = (
            "<div class=\"rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700\">"
            "子域跳转已创建"
            "</div>"
        )
        return HTMLResponse(
            message,
            status_code=status.HTTP_201_CREATED,
            headers={"HX-Trigger": "refresh-subdomains"},
        )

    body = SubdomainRedirectSchema.model_validate(redirect).model_dump(mode="json")
    return JSONResponse(
        body,
        status_code=status.HTTP_201_CREATED,
        headers={"HX-Trigger": "refresh-subdomains"},
    )


@app.delete(
    "/api/subdomains/{redirect_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_basic_auth)],
)
def delete_subdomain(
    redirect_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    """删除指定子域跳转。"""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")
    db.delete(redirect)
    db.commit()
    hx_request = request.headers.get("hx-request") == "true"
    if hx_request:
        message = (
            "<div class=\"rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700\">"
            "子域跳转已删除"
            "</div>"
        )
        return HTMLResponse(
            message,
            status_code=status.HTTP_200_OK,
            headers={"HX-Trigger": "refresh-subdomains"},
        )

    response.headers["HX-Trigger"] = "refresh-subdomains"
    return Response(status_code=status.HTTP_200_OK)


@app.get("/r/{code}")
def redirect_short_link(code: str, db: Session = Depends(get_db)) -> RedirectResponse:
    """公共短链接跳转入口，同时累计访问次数。"""

    short_link = db.scalar(select(ShortLink).where(ShortLink.code == code))
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")

    short_link.hits += 1
    db.add(short_link)
    db.commit()

    return RedirectResponse(short_link.target_url, status_code=status.HTTP_302_FOUND)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    response_model=None,
)
def catch_all(
    request: Request, path: str, db: Session = Depends(get_db)
) -> Response:
    """根据 Host 匹配子域跳转规则，否则返回 404 文本。"""

    host = (request.headers.get("host") or "").strip().lower()
    if not host:
        return PlainTextResponse("Not Found", status_code=status.HTTP_404_NOT_FOUND)

    redirect = db.scalar(select(SubdomainRedirect).where(SubdomainRedirect.host == host))
    if redirect is None:
        return PlainTextResponse("Not Found", status_code=status.HTTP_404_NOT_FOUND)

    destination = _compose_redirect_target(
        redirect.target_url, path=path, query=request.url.query or ""
    )
    return RedirectResponse(destination, status_code=redirect.code)
