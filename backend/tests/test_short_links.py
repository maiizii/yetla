from __future__ import annotations

ADMIN_AUTH = ("admin", "admin")


def test_create_short_link(client: "SimpleClient") -> None:
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["target_url"] == "https://example.com"
    assert payload["code"]
    assert payload["hits"] == 0


def test_create_short_link_conflict(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.com", "code": "custom"},
        auth=ADMIN_AUTH,
    )

    conflict = client.post(
        "/api/links",
        json={"target_url": "https://example.org", "code": "custom"},
        auth=ADMIN_AUTH,
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"error": "短链接编码已存在"}


def test_redirect_short_link_and_hits(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.com/landing", "code": "go"},
        auth=ADMIN_AUTH,
    )

    redirect = client.get("/r/go", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.com/landing"

    listing = client.get("/api/links", auth=ADMIN_AUTH)
    assert listing.status_code == 200
    records = listing.json()
    assert len(records) == 1
    assert records[0]["hits"] == 1


def test_redirect_short_link_not_found(client: "SimpleClient") -> None:
    response = client.get("/r/missing", follow_redirects=False)
    assert response.status_code == 404
    assert response.json() == {"error": "短链接不存在"}


def test_create_short_link_via_htmx_form(client: "SimpleClient") -> None:
    response = client.post(
        "/api/links",
        data={"target_url": "https://example.com/docs"},
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 201
    assert response.headers.get("hx-trigger") == "refresh-links"
    assert "短链创建成功" in response.text


def test_delete_short_link_via_htmx_button(client: "SimpleClient") -> None:
    created = client.post(
        "/api/links",
        json={"target_url": "https://example.com/remove", "code": "temp"},
        auth=ADMIN_AUTH,
    )
    link_id = created.json()["id"]

    response = client.delete(
        f"/api/links/{link_id}",
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 200
    assert response.headers.get("hx-trigger") == "refresh-links"
    assert "短链已删除" in response.text


def test_admin_short_link_partials(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.com/list", "code": "list"},
        auth=ADMIN_AUTH,
    )

    table = client.get("/admin/links/table", auth=ADMIN_AUTH)
    assert table.status_code == 200
    assert "短链编码" in table.text

    count = client.get("/admin/links/count", auth=ADMIN_AUTH)
    assert count.status_code == 200
    assert "short-link-count" in count.text
