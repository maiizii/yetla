"""HTML views for the administrative dashboard."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
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
