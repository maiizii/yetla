"""HTML views for the administrative dashboard."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .deps import get_db
from .models import ShortLink, SubdomainRedirect

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter()


def _load_short_links(db: Session) -> list[ShortLink]:
    return list(db.scalars(select(ShortLink).order_by(ShortLink.created_at.desc())).all())


def _load_subdomains(db: Session) -> list[SubdomainRedirect]:
    return list(
        db.scalars(select(SubdomainRedirect).order_by(SubdomainRedirect.created_at.desc())).all()
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    tab: str = Query("links"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render an authenticated dashboard for short links and subdomain redirects."""

    active_tab = tab if tab in {"links", "subdomains"} else "links"

    short_links = _load_short_links(db)
    subdomains = _load_subdomains(db)

    return templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "active_tab": active_tab,
            "short_links": short_links,
            "subdomains": subdomains,
        },
    )


@router.get("/admin/links/count", response_class=HTMLResponse)
def short_link_count(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a small fragment containing the current short link count."""

    short_links = _load_short_links(db)
    return templates.TemplateResponse(
        "admin/partials/link_count.html",
        {"request": request, "count": len(short_links)},
    )


@router.get("/admin/links/table", response_class=HTMLResponse)
def short_link_table(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the short link table fragment for HTMX swaps."""

    short_links = _load_short_links(db)
    return templates.TemplateResponse(
        "admin/partials/link_table.html",
        {"request": request, "short_links": short_links},
    )


@router.get("/admin/links/{link_id}/row", response_class=HTMLResponse)
def short_link_row(
    request: Request,
    link_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a single short link row for cancel/edit swaps."""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")

    return templates.TemplateResponse(
        "admin/partials/link_row.html",
        {"request": request, "item": short_link},
    )


@router.get("/admin/links/{link_id}/edit", response_class=HTMLResponse)
def short_link_edit_row(
    request: Request,
    link_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the editable row for a specific short link."""

    short_link = db.get(ShortLink, link_id)
    if short_link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="短链接不存在")

    return templates.TemplateResponse(
        "admin/partials/link_edit_row.html",
        {"request": request, "item": short_link},
    )


@router.get("/admin/subdomains/count", response_class=HTMLResponse)
def subdomain_count(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the current subdomain redirect count fragment."""

    subdomains = _load_subdomains(db)
    return templates.TemplateResponse(
        "admin/partials/subdomain_count.html",
        {"request": request, "count": len(subdomains)},
    )


@router.get("/admin/subdomains/table", response_class=HTMLResponse)
def subdomain_table(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the subdomain table fragment for HTMX swaps."""

    subdomains = _load_subdomains(db)
    return templates.TemplateResponse(
        "admin/partials/subdomain_table.html",
        {"request": request, "subdomains": subdomains},
    )


@router.get("/admin/subdomains/{redirect_id}/row", response_class=HTMLResponse)
def subdomain_row(
    request: Request,
    redirect_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return a single subdomain redirect row."""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")

    return templates.TemplateResponse(
        "admin/partials/subdomain_row.html",
        {"request": request, "item": redirect},
    )


@router.get("/admin/subdomains/{redirect_id}/edit", response_class=HTMLResponse)
def subdomain_edit_row(
    request: Request,
    redirect_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return the editable row for a subdomain redirect."""

    redirect = db.get(SubdomainRedirect, redirect_id)
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="子域跳转不存在")

    return templates.TemplateResponse(
        "admin/partials/subdomain_edit_row.html",
        {"request": request, "item": redirect},
    )
