"""FastAPI 应用，提供 yet.la 的短链接与子域跳转管理接口。"""
from __future__ import annotations

import os
import secrets
import string

from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .deps import get_db, require_basic_auth
from .models import Base, ShortLink, SubdomainRedirect, engine, ensure_subdomain_hits_column
from .schemas import (
    ShortLink as ShortLinkSchema,
    ShortLinkCreate,
    ShortLinkUpdate,
    SubdomainRedirect as SubdomainRedirectSchema,
    SubdomainRedirectCreate,
    SubdomainRedirectUpdate,
)
from pydantic import ValidationError

SHORT_CODE_LEN = int(os.getenv("SHORT_CODE_LEN", "6"))
MAX_CODE_ATTEMPTS = 10
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "").strip().lower()

app = FastAPI(
    title="Yetla Redirect API",
    description="管理短链接与子域跳转的受保护接口，并提供公共重定向入口。",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
)


from .views import (
    router as admin_router,
    templates as admin_templates,
)  # noqa: E402  pylint: disable=wrong-import-position

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(admin_router, dependencies=[Depends(require_basic_auth)])


@app.on_event("startup")
def ensure_tables() -> None:
    """应用启动时确保数据目录存在并创建数据库表。"""

    try:
        Path("/data").mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - 失败属于部署问题
        raise RuntimeError(f"failed to ensure /data directory: {exc}") from exc

    try:
        Base.metadata.create_all(bind=engine)
        ensure_subdomain_hits_column()
    except SQLAlchemyError as exc:  # pragma: no cover - 依赖数据库环境
        raise RuntimeError("failed to initialize database schema") from exc


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """为 404/409 返回统一结构，方便调用方解析。"""

    hx_request = request.headers.get("hx-request") == "true"
    headers = exc.headers or None
    if exc.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT}:
        if hx_request:
            return HTMLResponse(
                (
                    "<div class=\"rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700\">"
                    f"{exc.detail}"
                    "</div>"
                ),
                status_code=exc.status_code,
                headers=headers,
            )
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=headers)
    if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY and hx_request:
        return HTMLResponse(
            (
                "<div class=\"rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700\">"
                f"{_format_validation_errors(exc.detail)}"
                "</div>"
            ),
            status_code=exc.status_code,
            headers=headers,
        )
    if hx_request:
        return HTMLResponse(
            (
                "<div class=\"rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700\">"
                f"{exc.detail}"
                "</div>"
            ),
            status_code=exc.status_code,
            headers=headers,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=headers)


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


def _decode_urlencoded_form(body: bytes, charset: str = "utf-8") -> dict[str, Any]:
    """解析 application/x-www-form-urlencoded 请求体。"""

    try:
        text = body.decode(charset)
    except UnicodeDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="表单内容解码失败") from exc
    return {key: value for key, value in parse_qsl(text, keep_blank_values=False)}


async def _read_form_data(request: Request, content_type: str) -> dict[str, Any]:
    """读取表单数据，在缺失 python-multipart 时优雅降级。"""

    if content_type.startswith("application/x-www-form-urlencoded"):
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        body = await request.body()
        return _decode_urlencoded_form(body, charset=charset)

    try:
        form = await request.form()
    except AssertionError as exc:  # python-multipart 未安装
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="缺少 python-multipart 依赖，无法解析表单上传",
        ) from exc
    return {key: value for key, value in form.multi_items()}


async def _parse_short_link_payload(request: Request) -> ShortLinkCreate:
    """解析短链请求载荷，兼容 JSON 与表单提交。"""

    content_type = request.headers.get("content-type", "").lower()
    data: dict[str, Any]
    if content_type.startswith("application/json"):
        data = await request.json()
    else:
        data = await _read_form_data(request, content_type)

    try:
        return ShortLinkCreate.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - FastAPI 将统一处理
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


async def _parse_short_link_update_payload(request: Request) -> ShortLinkUpdate:
    """解析短链更新请求，兼容 JSON 与表单提交。"""

    content_type = request.headers.get("content-type", "").lower()
    data: dict[str, Any]
    if content_type.startswith("application/json"):
        data = await request.json()
    else:
        data = await _read_form_data(request, content_type)

    try:
        return ShortLinkUpdate.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - FastAPI 将统一处理
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


async def _parse_subdomain_payload(request: Request) -> SubdomainRedirectCreate:
    """解析子域跳转请求载荷，支持 JSON 与表单提交。"""

    content_type = request.headers.get("content-type", "").lower()
    data: dict[str, Any]
    if content_type.startswith("application/json"):
        data = await request.json()
    else:
        data = await _read_form_data(request, content_type)

    try:
        return SubdomainRedirectCreate.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - FastAPI 将统一处理
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


async def _parse_subdomain_update_payload(
    request: Request,
) -> SubdomainRedirectUpdate:
    """解析子域更新请求，支持 JSON 与表单提交。"""

    content_type = request.headers.get("content-type", "").lower()
    data: dict[str, Any]
    if content_type.startswith("application/json"):
        data = await request.json()
    else:
        data = await _read_form_data(request, content_type)

    try:
        return SubdomainRedirectUpdate.model_validate(data)
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


def _commit_session(db: Session, conflict_detail: str | None = None) -> None:
    """提交当前事务并在失败时转换为 HTTP 错误。"""

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = conflict_detail or "唯一约束冲突"
        raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc
    except SQLAlchemyError as exc:  # pragma: no cover - 依赖数据库环境
        db.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="数据库写入失败，请稍后再试",
        ) from exc


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
    response: Response,
    payload: ShortLinkCreate = Depends(_parse_short_link_payload),
    db: Session = Depends(get_db),
) -> ShortLink | HTMLResponse:
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
    _commit_session(db, conflict_detail="短链接编码已存在")
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
    response.headers["HX-Trigger"] = "refresh-links"
    return short_link


@app.delete(
    "/api/links/{link_id}",
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
    _commit_session(db)
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
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put(
    "/api/links/{link_id}",
    response_model=ShortLinkSchema,
    dependencies=[Depends(require_basic_auth)],
)
async def update_short_link(
    link_id: int,
    request: Request,
    response: Response,
    payload: ShortLinkUpdate = Depends(_parse_short_link_update_payload),
    db: Session = Depends(get_db),
) -> ShortLink | HTMLResponse:
    """更新指定短链接的编码或目标地址。"""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")

    if payload.code != short_link.code:
        exists = db.scalar(select(ShortLink).where(ShortLink.code == payload.code))
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="短链接编码已存在")

    short_link.code = payload.code
    short_link.target_url = payload.target_url
    db.add(short_link)
    _commit_session(db, conflict_detail="短链接编码已存在")
    db.refresh(short_link)

    hx_request = request.headers.get("hx-request") == "true"
    if hx_request:
        message = (
            "<div class=\"rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700\">"
            "短链已更新"
            "</div>"
        )
        row_html = admin_templates.get_template("admin/partials/link_row.html").render(
            {"request": request, "item": short_link, "oob": True}
        )
        content = f"{message}{row_html}"
        return HTMLResponse(
            content,
            status_code=status.HTTP_200_OK,
            headers={"HX-Trigger": "refresh-links"},
        )

    response.headers["HX-Trigger"] = "refresh-links"
    return short_link


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
    response: Response,
    payload: SubdomainRedirectCreate = Depends(_parse_subdomain_payload),
    db: Session = Depends(get_db),
) -> SubdomainRedirect | HTMLResponse:
    """创建子域跳转规则，Host 为完整域名。"""

    host = payload.host
    existing = db.scalar(select(SubdomainRedirect).where(SubdomainRedirect.host == host))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="子域跳转已存在")

    redirect = SubdomainRedirect(host=host, target_url=payload.target_url, code=payload.code)
    db.add(redirect)
    _commit_session(db, conflict_detail="子域跳转已存在")
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

    response.headers["HX-Trigger"] = "refresh-subdomains"
    return redirect


@app.delete(
    "/api/subdomains/{redirect_id}",
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
    _commit_session(db)
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
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put(
    "/api/subdomains/{redirect_id}",
    response_model=SubdomainRedirectSchema,
    dependencies=[Depends(require_basic_auth)],
)
async def update_subdomain(
    redirect_id: int,
    request: Request,
    response: Response,
    payload: SubdomainRedirectUpdate = Depends(_parse_subdomain_update_payload),
    db: Session = Depends(get_db),
) -> SubdomainRedirect | HTMLResponse:
    """更新子域跳转规则。"""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")

    normalized_host = payload.host
    if normalized_host != redirect.host:
        exists = db.scalar(
            select(SubdomainRedirect).where(SubdomainRedirect.host == normalized_host)
        )
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="子域跳转已存在")

    redirect.host = normalized_host
    redirect.target_url = payload.target_url
    redirect.code = payload.code
    db.add(redirect)
    _commit_session(db, conflict_detail="子域跳转已存在")
    db.refresh(redirect)

    hx_request = request.headers.get("hx-request") == "true"
    if hx_request:
        message = (
            "<div class=\"rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700\">"
            "子域跳转已更新"
            "</div>"
        )
        row_html = admin_templates.get_template("admin/partials/subdomain_row.html").render(
            {"request": request, "item": redirect, "oob": True}
        )
        content = f"{message}{row_html}"
        return HTMLResponse(
            content,
            status_code=status.HTTP_200_OK,
            headers={"HX-Trigger": "refresh-subdomains"},
        )

    response.headers["HX-Trigger"] = "refresh-subdomains"
    return redirect


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def catch_all(
    request: Request, path: str, db: Session = Depends(get_db)
) -> Response:
    """根据 Host 匹配子域跳转规则，否则返回 404 文本。"""

    raw_host = (request.headers.get("host") or "").strip().lower()
    if not raw_host:
        return PlainTextResponse("Not Found", status_code=status.HTTP_404_NOT_FOUND)
    host = raw_host.split(":", 1)[0]

    redirect = db.scalar(select(SubdomainRedirect).where(SubdomainRedirect.host == host))
    if redirect is not None:
        redirect.hits += 1
        db.add(redirect)
        _commit_session(db)

        destination = _compose_redirect_target(
            redirect.target_url, path=path, query=request.url.query or ""
        )
        return RedirectResponse(destination, status_code=redirect.code)

    allow_short_link = not BASE_DOMAIN or host == BASE_DOMAIN

    if allow_short_link and request.method in {"GET", "HEAD"}:
        code = path.strip("/")
        if code and "/" not in code:
            short_link = db.scalar(select(ShortLink).where(ShortLink.code == code))
            if short_link is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")

            short_link.hits += 1
            db.add(short_link)
            _commit_session(db)

            return RedirectResponse(
                short_link.target_url, status_code=status.HTTP_302_FOUND
            )

    return PlainTextResponse("Not Found", status_code=status.HTTP_404_NOT_FOUND)
