from __future__ import annotations

ADMIN_AUTH = ("admin", "admin")


def test_routes_endpoint_lists_subdomains(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "a.test", "target_url": "https://example.com/a"},
        auth=ADMIN_AUTH,
    )
    client.post(
        "/api/subdomains",
        json={"host": "b.test", "target_url": "https://example.com/b"},
        auth=ADMIN_AUTH,
    )

    response = client.get("/routes")
    assert response.status_code == 200
    hosts = [item["host"] for item in response.json()]
    assert hosts == ["a.test", "b.test"]
