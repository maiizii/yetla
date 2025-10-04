ADMIN_AUTH = ("admin", "admin")


def test_admin_can_create_update_delete_user(client: "SimpleClient") -> None:
    created = client.post(
        "/api/users",
        json={
            "username": "tester",
            "email": "tester@example.com",
            "password": "testpass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["username"] == "tester"
    assert payload["email"] == "tester@example.com"
    assert payload["is_admin"] is False

    updated = client.put(
        f"/api/users/{payload['id']}",
        data={
            "username": "tester",
            "email": "new@example.com",
            "password": "newpass",
            "password_confirm": "newpass",
            "is_admin": "1",
        },
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert updated.status_code == 200
    assert "用户信息已更新" in updated.text
    assert updated.headers.get("hx-trigger") == "refresh-users"

    deleted = client.delete(
        f"/api/users/{payload['id']}",
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert deleted.status_code == 200
    assert "用户已删除" in deleted.text
    assert deleted.headers.get("hx-trigger") == "refresh-users"


def test_non_admin_cannot_access_user_management(client: "SimpleClient") -> None:
    client.post(
        "/api/users",
        json={
            "username": "limited",
            "email": "limited@example.com",
            "password": "limitedpass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    user_auth = ("limited", "limitedpass")

    listing = client.get("/api/users", auth=user_auth)
    assert listing.status_code == 403
    assert listing.json()["detail"] == "需要管理员权限"

    creation = client.post(
        "/api/users",
        json={
            "username": "other",
            "email": "other@example.com",
            "password": "otherpass",
            "is_admin": False,
        },
        auth=user_auth,
    )
    assert creation.status_code == 403
    assert creation.json()["detail"] == "需要管理员权限"


def test_admin_user_partials(client: "SimpleClient") -> None:
    client.post(
        "/api/users",
        json={
            "username": "viewer",
            "email": "viewer@example.com",
            "password": "viewerpass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    table = client.get("/admin/users/table", auth=ADMIN_AUTH)
    assert table.status_code == 200
    assert "viewer@example.com" in table.text

    count = client.get("/admin/users/count", auth=ADMIN_AUTH)
    assert count.status_code == 200
    assert "user-count" in count.text
