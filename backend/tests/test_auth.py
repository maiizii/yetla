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
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/login")


def test_login_flow_success(client: "SimpleClient") -> None:
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert "登录 yet.la 短链子域管理后台" in response.text

    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200
    assert "创建短链" in response.text
    assert "修改密码" in response.text

    dashboard = client.get("/admin", follow_redirects=False)
    assert dashboard.status_code == 200


def test_login_flow_failure_feedback(client: "SimpleClient") -> None:
    response = client.post(
        "/admin/login",
        data={"username": "wrong", "password": "admin"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "账号错误" in response.text

    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "oops"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "密码错误" in response.text


def test_logout_clears_session(client: "SimpleClient") -> None:
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin"},
    )

    response = client.get("/admin/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/login")

    login_page = client.get("/admin/login")
    assert login_page.status_code == 200
    assert "登录 yet.la 短链子域管理后台" in login_page.text

    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/login")


def test_change_password_flow(client: "SimpleClient") -> None:
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin"},
    )

    page = client.get("/admin/password")
    assert page.status_code == 200
    assert "修改密码" in page.text

    response = client.post(
        "/api/users/me/password",
        data={
            "current_password": "admin",
            "new_password": "changed123",
            "confirm_password": "changed123",
        },
        headers={"hx-request": "true"},
    )
    assert response.status_code == 200
    assert "密码修改成功" in response.text

    client.get("/admin/logout")

    bad_login = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=False,
    )
    assert bad_login.status_code == 400
    assert "密码错误" in bad_login.text

    good_login = client.post(
        "/admin/login",
        data={"username": "admin", "password": "changed123"},
    )
    assert good_login.status_code == 200
