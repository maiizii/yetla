"""HTML views for the administrative dashboard."""
from __future__ import annotations

import os
import secrets
import string
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .deps import get_db, require_admin_auth, validate_credentials
from .session import clear_session, get_session, set_session
from .models import ShortLink, SubdomainRedirect

DEFAULT_BASE_DOMAIN = "yet.la"
SHORT_CODE_LENGTH = int(os.getenv("SHORT_CODE_LEN", "6"))
ENV_BASE_DOMAIN = os.getenv("BASE_DOMAIN", "").strip().lower()
EFFECTIVE_BASE_DOMAIN = ENV_BASE_DOMAIN or DEFAULT_BASE_DOMAIN
BASE_URL = f"https://{EFFECTIVE_BASE_DOMAIN}".rstrip("/")
SHORT_LINK_PREFIX = f"{BASE_URL}/"
SUBDOMAIN_CODE_OPTIONS = [302, 301]

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter()


def _safe_redirect_target(target: str | None) -> str:
    if not target:
        return "/admin"
    if target.startswith("http://") or target.startswith("https://"):
        return "/admin"
    if not target.startswith("/"):
        return "/admin"
    return target


def _load_short_links(db: Session) -> list[ShortLink]:
    return list(db.scalars(select(ShortLink).order_by(ShortLink.created_at.desc())).all())


def _load_subdomains(db: Session) -> list[SubdomainRedirect]:
    return list(
        db.scalars(select(SubdomainRedirect).order_by(SubdomainRedirect.created_at.desc())).all()
    )


def _generate_short_link_suggestion(db: Session, length: int = SHORT_CODE_LENGTH) -> str:
    """Generate a random short link code suggestion that does not clash with existing ones."""

    alphabet = string.ascii_letters + string.digits
    attempts = max(length * 2, 10)
    for _ in range(attempts):
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = db.scalar(select(ShortLink.id).where(ShortLink.code == candidate))
        if not exists:
            return candidate
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _base_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "base_domain": EFFECTIVE_BASE_DOMAIN,
        "base_url": BASE_URL,
        "short_link_prefix": SHORT_LINK_PREFIX,
        "short_code_length": SHORT_CODE_LENGTH,
        "show_logout_button": True,
    }


@router.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_admin_auth)])
def admin_dashboard(
    request: Request,
    tab: str = Query("links"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render an authenticated dashboard for short links and subdomain redirects."""

    active_tab = tab if tab in {"links", "subdomains"} else "links"

    short_links = _load_short_links(db)
    subdomains = _load_subdomains(db)

    context = _base_context(request)
    context.update(
        {
            "active_tab": active_tab,
            "short_links": short_links,
            "subdomains": subdomains,
            "short_code_suggestion": _generate_short_link_suggestion(db),
            "subdomain_code_options": SUBDOMAIN_CODE_OPTIONS,
        }
    )
    return templates.TemplateResponse("admin/index.html", context)


@router.get("/admin/logout", response_class=HTMLResponse, dependencies=[Depends(require_admin_auth)])
def admin_logout(request: Request) -> RedirectResponse:
    """Clear session state and redirect to the login page."""

    response = RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_session(response, request)
    return response


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(
    request: Request,
    redirect_to: str | None = Query(default=None, alias="next"),
) -> HTMLResponse:
    """Render the login page using the dashboard theme."""

    session = get_session(request)
    if session.get("is_authenticated"):
        target = _safe_redirect_target(redirect_to)
        return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)

    context = _base_context(request)
    context.update(
        {
            "show_logout_button": False,
            "redirect_target": redirect_to,
            "login_error": None,
            "username_value": "",
        }
    )
    return templates.TemplateResponse("admin/login.html", context)


@router.post("/admin/login", response_class=HTMLResponse)
async def admin_login_submit(
    request: Request,
    redirect_to: str | None = Query(default=None, alias="next"),
) -> HTMLResponse:
    """Handle login submissions and persist session state on success."""

    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""

    error: str | None = None
    if not username or not password:
        error = "账号或密码不能为空"
    else:
        ok, reason = validate_credentials(username, password)
        if ok:
            target = _safe_redirect_target(redirect_to)
            response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
            set_session(response, request, {"is_authenticated": True, "username": username})
            return response
        if reason == "username":
            error = "账号错误"
        elif reason == "password":
            error = "密码错误"
        else:
            error = "登录失败"

    context = _base_context(request)
    context.update(
        {
            "show_logout_button": False,
            "redirect_target": redirect_to,
            "login_error": error,
            "username_value": username,
        }
    )
    status_code = status.HTTP_400_BAD_REQUEST if error else status.HTTP_200_OK
    return templates.TemplateResponse(
        "admin/login.html",
        context,
        status_code=status_code,
    )


@router.get(
    "/admin/links/count",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def short_link_count(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a small fragment containing the current short link count."""

    short_links = _load_short_links(db)
    context = _base_context(request)
    context.update({"count": len(short_links)})
    return templates.TemplateResponse("admin/partials/link_count.html", context)


@router.get(
    "/admin/links/table",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def short_link_table(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the short link table fragment for HTMX swaps."""

    short_links = _load_short_links(db)
    context = _base_context(request)
    context.update({"short_links": short_links})
    return templates.TemplateResponse("admin/partials/link_table.html", context)


@router.get(
    "/admin/links/{link_id}/row",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def short_link_row(
    request: Request,
    link_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a single short link row for cancel/edit swaps."""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")

    context = _base_context(request)
    context.update({"item": short_link})
    return templates.TemplateResponse("admin/partials/link_row.html", context)


@router.get(
    "/admin/links/{link_id}/edit",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def short_link_edit_row(
    request: Request,
    link_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the editable row for a specific short link."""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")

    context = _base_context(request)
    context.update({"item": short_link})
    return templates.TemplateResponse("admin/partials/link_edit_row.html", context)


@router.get(
    "/admin/subdomains/count",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def subdomain_count(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the current subdomain redirect count fragment."""

    subdomains = _load_subdomains(db)
    context = _base_context(request)
    context.update({"count": len(subdomains)})
    return templates.TemplateResponse("admin/partials/subdomain_count.html", context)


@router.get(
    "/admin/subdomains/table",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def subdomain_table(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the subdomain table fragment for HTMX swaps."""

    subdomains = _load_subdomains(db)
    context = _base_context(request)
    context.update({"subdomains": subdomains})
    return templates.TemplateResponse("admin/partials/subdomain_table.html", context)


@router.get(
    "/admin/subdomains/{redirect_id}/row",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def subdomain_row(
    request: Request,
    redirect_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a single subdomain redirect row."""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")

    context = _base_context(request)
    context.update({"item": redirect})
    return templates.TemplateResponse("admin/partials/subdomain_row.html", context)


@router.get(
    "/admin/subdomains/{redirect_id}/edit",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin_auth)],
)
def subdomain_edit_row(
    request: Request,
    redirect_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the editable row for a subdomain redirect."""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")

    context = _base_context(request)
    context.update({"item": redirect, "subdomain_code_options": SUBDOMAIN_CODE_OPTIONS})
    return templates.TemplateResponse("admin/partials/subdomain_edit_row.html", context)
