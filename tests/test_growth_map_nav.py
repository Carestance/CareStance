from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app import main


class _ScalarsResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _FakeDatabase:
    def __init__(self, *values):
        self.values = list(values)
        self.query_count = 0

    async def execute(self, _statement):
        self.query_count += 1
        return _ScalarsResult(self.values.pop(0))


def _request(accept: str) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/dashboard",
        "raw_path": b"/dashboard",
        "query_string": b"",
        "headers": [
            (b"accept", accept.encode()),
            (b"cookie", b"user_id=test-token"),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    })


@pytest.mark.asyncio
async def test_growth_map_nav_url_is_url_encoded(monkeypatch):
    user = SimpleNamespace(id=42, role="student")
    plan = SimpleNamespace(career_title="Data & AI/ML")
    db = _FakeDatabase(user, plan)
    monkeypatch.setattr(main, "decode_access_token", lambda _token: 42)
    request = _request("text/html")

    result = await main.get_current_user(request, db)

    assert result is user
    assert request.state.growth_map_url == "/my-monthly-path?career=Data%20%26%20AI%2FML"
    assert db.query_count == 2


@pytest.mark.asyncio
async def test_growth_map_nav_url_is_absent_before_map_generation(monkeypatch):
    user = SimpleNamespace(id=42, role="student")
    db = _FakeDatabase(user, None)
    monkeypatch.setattr(main, "decode_access_token", lambda _token: 42)
    request = _request("text/html")

    result = await main.get_current_user(request, db)

    assert result is user
    assert request.state.growth_map_url is None


@pytest.mark.asyncio
async def test_non_html_requests_skip_growth_map_lookup(monkeypatch):
    user = SimpleNamespace(id=42, role="student")
    db = _FakeDatabase(user)
    monkeypatch.setattr(main, "decode_access_token", lambda _token: 42)
    request = _request("application/json")

    result = await main.get_current_user(request, db)

    assert result is user
    assert not hasattr(request.state, "growth_map_url")
    assert db.query_count == 1
