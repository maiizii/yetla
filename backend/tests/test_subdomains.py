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


def test_host_redirect_not_found(client: "SimpleClient") -> None:
    response = client.get("/", headers={"host": "unknown.test"}, follow_redirects=False)
    assert response.status_code == 404
    assert response.text == "Not Found"
