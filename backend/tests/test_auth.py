from __future__ import annotations

def test_protected_endpoints_require_basic_auth(client: "SimpleClient") -> None:
    response = client.get("/api/links")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"

    response = client.post(
        "/api/subdomains",
        json={"host": "secure.test", "target_url": "https://example.com"},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


def test_admin_dashboard_requires_basic_auth(client: "SimpleClient") -> None:
    response = client.get("/admin")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"
