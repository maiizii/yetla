from __future__ import annotations

import asyncio
import base64
import json
import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pytest
from sqlalchemy import delete

TEST_DB_PATH = Path(__file__).resolve().parent / "test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from backend.app.main import app  # noqa: E402  pylint: disable=wrong-import-position
from backend.app.models import (  # noqa: E402  pylint: disable=wrong-import-position
    Base,
    SessionLocal,
    ShortLink,
    SubdomainRedirect,
    engine,
)

REDIRECT_STATUSES = {301, 302, 303, 307, 308}


@dataclass
class _Headers:
    _items: dict[str, str]

    def __contains__(self, key: str) -> bool:  # pragma: no cover - helper
        return key.lower() in self._items

    def __getitem__(self, key: str) -> str:
        return self._items[key.lower()]

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._items.get(key.lower(), default)

    def items(self) -> Iterable[tuple[str, str]]:  # pragma: no cover - helper
        return self._items.items()


class SimpleResponse:
    def __init__(self, status_code: int, headers: Iterable[tuple[str, str]], body: bytes) -> None:
        self.status_code = status_code
        self.headers = _Headers({k.lower(): v for k, v in headers})
        self._body = body

    def json(self) -> Any:
        if not self._body:
            return None
        return json.loads(self._body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self._body.decode("utf-8")


class SimpleClient:
    def __init__(self) -> None:
        self._app = app

    def _run_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> SimpleResponse:
        path, _, query = url.partition("?")
        raw_path = path.encode("ascii", "ignore")
        header_items = [
            (key.encode("latin-1"), value.encode("latin-1"))
            for key, value in headers.items()
        ]

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method.upper(),
            "path": path,
            "raw_path": raw_path,
            "root_path": "",
            "scheme": "http",
            "query_string": query.encode("latin-1"),
            "headers": header_items,
            "client": ("testclient", 1234),
            "server": (headers.get("host", "testserver"), 80),
        }

        messages: list[dict[str, Any]] = []
        body_sent = False

        async def receive() -> dict[str, Any]:
            nonlocal body_sent
            if body_sent:
                return {"type": "http.disconnect"}
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        asyncio.run(self._app(scope, receive, send))

        status = 500
        response_headers: list[tuple[str, str]] = []
        chunks: list[bytes] = []
        for message in messages:
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = [
                    (key.decode("latin-1"), value.decode("latin-1"))
                    for key, value in message.get("headers", [])
                ]
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        return SimpleResponse(status, response_headers, b"".join(chunks))

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any | None = None,
        data: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> SimpleResponse:
        prepared_headers = {k.lower(): v for k, v in (headers or {}).items()}
        prepared_headers.setdefault("host", "testserver")
        body = b""
        if json_body is not None and data is not None:
            raise ValueError("json_body and data cannot be provided together")
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            prepared_headers.setdefault("content-type", "application/json")
        elif data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            prepared_headers.setdefault(
                "content-type", "application/x-www-form-urlencoded"
            )

        if auth is not None:
            token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode("utf-8")).decode("ascii")
            prepared_headers["authorization"] = f"Basic {token}"

        response = self._run_request(method, url, headers=prepared_headers, body=body)
        if (
            follow_redirects
            and response.status_code in REDIRECT_STATUSES
            and response.headers.get("location")
        ):
            location = response.headers["location"]
            next_url = location
            if location.startswith("http://") or location.startswith("https://"):
                parts = location.split("://", 1)[1]
                next_url = parts[parts.find("/") :] if "/" in parts else "/"
            redirect_method = "GET" if response.status_code in {301, 302, 303} else method
            return self.request(
                redirect_method,
                next_url,
                headers=headers,
                auth=auth,
                follow_redirects=follow_redirects,
            )
        return response

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> SimpleResponse:
        return self.request(
            "GET",
            url,
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
        )

    def post(
        self,
        url: str,
        *,
        json: Any | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> SimpleResponse:
        return self.request(
            "POST",
            url,
            headers=headers,
            json_body=json,
            data=data,
            auth=auth,
            follow_redirects=follow_redirects,
        )

    def put(
        self,
        url: str,
        *,
        json: Any | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> SimpleResponse:
        return self.request(
            "PUT",
            url,
            headers=headers,
            json_body=json,
            data=data,
            auth=auth,
            follow_redirects=follow_redirects,
        )

    def delete(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> SimpleResponse:
        return self.request(
            "DELETE",
            url,
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
        )


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(autouse=True)
def _clean_database() -> None:
    with SessionLocal() as session:
        session.execute(delete(ShortLink))
        session.execute(delete(SubdomainRedirect))
        session.commit()
    yield
    with SessionLocal() as session:
        session.execute(delete(ShortLink))
        session.execute(delete(SubdomainRedirect))
        session.commit()


@pytest.fixture()
def client() -> SimpleClient:
    return SimpleClient()
