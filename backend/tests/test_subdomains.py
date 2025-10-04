from __future__ import annotations

ADMIN_AUTH = ("admin", "admin")


def test_create_subdomain(client: "SimpleClient") -> None:
    response = client.post(
        "/api/subdomains",
        json={"host": "docs.test", "target_url": "https://example.com/docs", "code": 301},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["host"] == "docs.test"
    assert payload["target_url"] == "https://example.com/docs"
    assert payload["code"] == 301
    assert payload["hits"] == 0


def test_create_subdomain_conflict(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "api.test", "target_url": "https://example.com/api"},
        auth=ADMIN_AUTH,
    )

    conflict = client.post(
        "/api/subdomains",
        json={"host": "api.test", "target_url": "https://example.org/api"},
        auth=ADMIN_AUTH,
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"error": "子域跳转已存在"}


def test_delete_subdomain(client: "SimpleClient") -> None:
    created = client.post(
        "/api/subdomains",
        json={"host": "remove.test", "target_url": "https://example.com/remove"},
        auth=ADMIN_AUTH,
    ).json()

    deleted = client.delete(f"/api/subdomains/{created['id']}", auth=ADMIN_AUTH)
    assert deleted.status_code == 204

    fallback = client.get("/", headers={"host": "remove.test"}, follow_redirects=False)
    assert fallback.status_code == 404
    assert fallback.text == "Not Found"


def test_update_subdomain_via_htmx_form(client: "SimpleClient") -> None:
    created = client.post(
        "/api/subdomains",
        json={"host": "edit.test", "target_url": "https://example.com/old"},
        auth=ADMIN_AUTH,
    ).json()

    response = client.put(
        f"/api/subdomains/{created['id']}",
        data={"host": "edit.test", "target_url": "https://example.com/new", "code": "301"},
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 200
    assert response.headers.get("hx-trigger") == "refresh-subdomains"
    assert "子域跳转已更新" in response.text
    assert "subdomain-row" in response.text
    assert "hx-swap-oob=\"outerHTML\"" in response.text

    listing = client.get("/api/subdomains", auth=ADMIN_AUTH)
    records = listing.json()
    assert records[0]["target_url"] == "https://example.com/new"
    assert records[0]["code"] == 301


def test_host_redirect_status_codes(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "legacy.test", "target_url": "https://legacy.example.com", "code": 301},
        auth=ADMIN_AUTH,
    )
    client.post(
        "/api/subdomains",
        json={"host": "www.test", "target_url": "https://www.example.com"},
        auth=ADMIN_AUTH,
    )

    permanent = client.get(
        "/path", headers={"host": "legacy.test"}, follow_redirects=False
    )
    assert permanent.status_code == 301
    assert permanent.headers["location"] == "https://legacy.example.com/path"

    temporary = client.get(
        "/docs?id=1", headers={"host": "www.test"}, follow_redirects=False
    )
    assert temporary.status_code == 302
    assert (
        temporary.headers["location"]
        == "https://www.example.com/docs?id=1"
    )


def test_subdomain_redirect_increments_hits(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "count.test", "target_url": "https://example.com/hits"},
        auth=ADMIN_AUTH,
    )

    for _ in range(3):
        response = client.get(
            "/path",
            headers={"host": "count.test"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    listing = client.get("/api/subdomains", auth=ADMIN_AUTH)
    assert listing.status_code == 200
    record = listing.json()[0]
    assert record["hits"] == 3


def test_permanent_redirect_counts_hits(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "permanent.test", "target_url": "https://example.com/permanent", "code": 301},
        auth=ADMIN_AUTH,
    )

    response = client.get(
        "/docs",
        headers={"host": "permanent.test"},
        follow_redirects=False,
    )
    assert response.status_code == 301

    listing = client.get("/api/subdomains", auth=ADMIN_AUTH)
    assert listing.status_code == 200
    record = next(item for item in listing.json() if item["host"] == "permanent.test")
    assert record["hits"] == 1


def test_host_redirect_not_found(client: "SimpleClient") -> None:
    response = client.get("/", headers={"host": "unknown.test"}, follow_redirects=False)
    assert response.status_code == 404
    assert response.text == "Not Found"


def test_admin_subdomain_table_includes_user_column(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "table.test", "target_url": "https://example.com"},
        auth=ADMIN_AUTH,
    )

    table = client.get("/admin/subdomains/table", auth=ADMIN_AUTH)
    assert table.status_code == 200
    assert "<th scope=\"col\">用户</th>" in table.text


def test_subdomains_are_scoped_by_user(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "admin-only.test", "target_url": "https://admin.example.com"},
        auth=ADMIN_AUTH,
    )

    client.post(
        "/api/users",
        json={
            "username": "charlie",
            "email": "charlie@example.com",
            "password": "charliepw",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    user_auth = ("charlie", "charliepw")
    client.post(
        "/api/subdomains",
        json={"host": "user.test", "target_url": "https://user.example.com"},
        auth=user_auth,
    )

    user_listing = client.get("/api/subdomains", auth=user_auth)
    assert user_listing.status_code == 200
    user_records = user_listing.json()
    assert len(user_records) == 1
    assert user_records[0]["host"] == "user.test"

    admin_listing = client.get("/api/subdomains", auth=ADMIN_AUTH)
    admin_hosts = {record["host"] for record in admin_listing.json()}
    assert admin_hosts == {"admin-only.test", "user.test"}


def test_non_admin_cannot_modify_other_subdomains(client: "SimpleClient") -> None:
    admin_redirect = client.post(
        "/api/subdomains",
        json={"host": "lock.test", "target_url": "https://secure.example.com"},
        auth=ADMIN_AUTH,
    ).json()

    client.post(
        "/api/users",
        json={
            "username": "dave",
            "email": "dave@example.com",
            "password": "davepass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    user_auth = ("dave", "davepass")

    forbidden_delete = client.delete(
        f"/api/subdomains/{admin_redirect['id']}",
        auth=user_auth,
    )
    assert forbidden_delete.status_code == 403
    assert forbidden_delete.json()["detail"] == "无权操作该子域"

    forbidden_update = client.put(
        f"/api/subdomains/{admin_redirect['id']}",
        json={"host": "lock.test", "target_url": "https://evil.example.com", "code": 302},
        auth=user_auth,
    )
    assert forbidden_update.status_code == 403
    assert forbidden_update.json()["detail"] == "无权操作该子域"
