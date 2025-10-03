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
