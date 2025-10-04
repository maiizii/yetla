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
from sqlalchemy.orm import Session, selectinload

from .deps import (
    establish_session,
    get_db,
    require_admin_user,
    require_authenticated_user,
    validate_credentials,
)
from .session import clear_session, get_session
from .models import ShortLink, SubdomainRedirect, User

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


def _load_short_links(db: Session, user: User) -> list[ShortLink]:
    query = select(ShortLink).options(selectinload(ShortLink.owner)).order_by(
        ShortLink.created_at.desc()
    )
    if not user.is_admin:
        query = query.where(ShortLink.user_id == user.id)
    return list(db.scalars(query).all())


def _load_subdomains(db: Session, user: User) -> list[SubdomainRedirect]:
    query = select(SubdomainRedirect).options(selectinload(SubdomainRedirect.owner)).order_by(
        SubdomainRedirect.created_at.desc()
    )
    if not user.is_admin:
        query = query.where(SubdomainRedirect.user_id == user.id)
    return list(db.scalars(query).all())


def _load_users(db: Session) -> list[User]:
    return list(
        db.scalars(select(User).order_by(User.created_at.desc())).all()
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


def _base_context(request: Request, user: User | None = None) -> dict[str, Any]:
    return {
        "request": request,
        "base_domain": EFFECTIVE_BASE_DOMAIN,
        "base_url": BASE_URL,
        "short_link_prefix": SHORT_LINK_PREFIX,
        "short_code_length": SHORT_CODE_LENGTH,
        "show_logout_button": True,
        "current_user": user,
    }


def _ensure_link_access(short_link: ShortLink, user: User) -> None:
    if user.is_admin:
        return
    if short_link.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="无权查看该短链")


def _ensure_subdomain_access(redirect: SubdomainRedirect, user: User) -> None:
    if user.is_admin:
        return
    if redirect.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="无权查看该子域")


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    tab: str = Query("links"),
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render an authenticated dashboard for short links and subdomain redirects."""

    available_tabs = {"links", "subdomains"}
    if current_user.is_admin:
        available_tabs.add("users")
    active_tab = tab if tab in available_tabs else "links"

    short_links = _load_short_links(db, current_user)
    subdomains = _load_subdomains(db, current_user)
    users: list[User] = _load_users(db) if current_user.is_admin else []

    context = _base_context(request, current_user)
    context.update(
        {
            "active_tab": active_tab,
            "short_links": short_links,
            "subdomains": subdomains,
            "users": users,
            "short_code_suggestion": _generate_short_link_suggestion(db),
            "subdomain_code_options": SUBDOMAIN_CODE_OPTIONS,
            "show_user_column": current_user.is_admin,
        }
    )
    return templates.TemplateResponse("admin/index.html", context)


@router.get("/admin/logout", response_class=HTMLResponse)
def admin_logout(
    request: Request, current_user: User = Depends(require_authenticated_user)
) -> RedirectResponse:
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
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Handle login submissions and persist session state on success."""

    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""

    error: str | None = None
    if not username or not password:
        error = "账号或密码不能为空"
    else:
        ok, reason, user = validate_credentials(username, password, db)
        if ok and user is not None:
            target = _safe_redirect_target(redirect_to)
            response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
            establish_session(response, request, user)
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
)
def short_link_count(
    request: Request,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a small fragment containing the current short link count."""

    short_links = _load_short_links(db, current_user)
    context = _base_context(request, current_user)
    context.update({"count": len(short_links)})
    return templates.TemplateResponse("admin/partials/link_count.html", context)


@router.get(
    "/admin/links/table",
    response_class=HTMLResponse,
)
def short_link_table(
    request: Request,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the short link table fragment for HTMX swaps."""

    short_links = _load_short_links(db, current_user)
    context = _base_context(request, current_user)
    context.update({"short_links": short_links, "show_user_column": current_user.is_admin})
    return templates.TemplateResponse("admin/partials/link_table.html", context)


@router.get(
    "/admin/links/{link_id}/row",
    response_class=HTMLResponse,
)
def short_link_row(
    request: Request,
    link_id: int,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a single short link row for cancel/edit swaps."""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")
    _ensure_link_access(short_link, current_user)

    context = _base_context(request, current_user)
    context.update({"item": short_link, "show_user_column": current_user.is_admin})
    return templates.TemplateResponse("admin/partials/link_row.html", context)


@router.get(
    "/admin/links/{link_id}/edit",
    response_class=HTMLResponse,
)
def short_link_edit_row(
    request: Request,
    link_id: int,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the editable row for a specific short link."""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")
    _ensure_link_access(short_link, current_user)

    context = _base_context(request, current_user)
    context.update({"item": short_link, "show_user_column": current_user.is_admin})
    return templates.TemplateResponse("admin/partials/link_edit_row.html", context)


@router.get(
    "/admin/subdomains/count",
    response_class=HTMLResponse,
)
def subdomain_count(
    request: Request,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the current subdomain redirect count fragment."""

    subdomains = _load_subdomains(db, current_user)
    context = _base_context(request, current_user)
    context.update({"count": len(subdomains)})
    return templates.TemplateResponse("admin/partials/subdomain_count.html", context)


@router.get(
    "/admin/subdomains/table",
    response_class=HTMLResponse,
)
def subdomain_table(
    request: Request,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the subdomain table fragment for HTMX swaps."""

    subdomains = _load_subdomains(db, current_user)
    context = _base_context(request, current_user)
    context.update({"subdomains": subdomains, "show_user_column": current_user.is_admin})
    return templates.TemplateResponse("admin/partials/subdomain_table.html", context)


@router.get(
    "/admin/subdomains/{redirect_id}/row",
    response_class=HTMLResponse,
)
def subdomain_row(
    request: Request,
    redirect_id: int,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a single subdomain redirect row."""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")
    _ensure_subdomain_access(redirect, current_user)

    context = _base_context(request, current_user)
    context.update({"item": redirect, "show_user_column": current_user.is_admin})
    return templates.TemplateResponse("admin/partials/subdomain_row.html", context)


@router.get(
    "/admin/subdomains/{redirect_id}/edit",
    response_class=HTMLResponse,
)
def subdomain_edit_row(
    request: Request,
    redirect_id: int,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the editable row for a subdomain redirect."""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")
    _ensure_subdomain_access(redirect, current_user)

    context = _base_context(request, current_user)
    context.update(
        {
            "item": redirect,
            "subdomain_code_options": SUBDOMAIN_CODE_OPTIONS,
            "show_user_column": current_user.is_admin,
        }
    )
    return templates.TemplateResponse("admin/partials/subdomain_edit_row.html", context)


@router.get(
    "/admin/users/count",
    response_class=HTMLResponse,
)
def user_count(
    request: Request,
    admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the current user count fragment."""

    users = _load_users(db)
    context = _base_context(request, admin)
    context.update({"count": len(users)})
    return templates.TemplateResponse("admin/partials/user_count.html", context)


@router.get(
    "/admin/users/table",
    response_class=HTMLResponse,
)
def user_table(
    request: Request,
    admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the user management table."""

    users = _load_users(db)
    context = _base_context(request, admin)
    context.update({"users": users})
    return templates.TemplateResponse("admin/partials/user_table.html", context)


@router.get(
    "/admin/users/{user_id}/row",
    response_class=HTMLResponse,
)
def user_row(
    request: Request,
    user_id: int,
    admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a single user row."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")

    context = _base_context(request, admin)
    context.update({"item": user})
    return templates.TemplateResponse("admin/partials/user_row.html", context)


@router.get(
    "/admin/users/{user_id}/edit",
    response_class=HTMLResponse,
)
def user_edit_row(
    request: Request,
    user_id: int,
    admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return an editable row for a user."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")

    context = _base_context(request, admin)
    context.update({"item": user})
    return templates.TemplateResponse("admin/partials/user_edit_row.html", context)


@router.get("/admin/password", response_class=HTMLResponse)
def password_page(
    request: Request,
    current_user: User = Depends(require_authenticated_user),
) -> HTMLResponse:
    """Render the password change form for the current user."""

    context = _base_context(request, current_user)
    context.update({"show_logout_button": True})
    return templates.TemplateResponse("admin/password.html", context)
