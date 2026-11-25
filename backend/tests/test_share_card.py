"""Lot A — Open Graph share card for public links (/s/<public_id>)."""
import asyncio

import pytest
from starlette.requests import Request

from routers import share_router
from routers.share_router import _is_crawler, _og_image


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None


class FakeDB:
    def __init__(self, restaurants):
        self.restaurants = FakeCollection(restaurants)


def _restaurant(**overrides):
    doc = {"_id": "rid-1", "public_id": "rest_demo_chezawa", "status": "active",
           "name": "Chez Awa", "description": "Maquis ivoirien", "logo": ""}
    doc.update(overrides)
    return doc


def _request(user_agent="Mozilla/5.0", query=""):
    return Request({
        "type": "http", "method": "GET", "path": "/share/rest_demo_chezawa",
        "query_string": query.encode(), "headers": [(b"user-agent", user_agent.encode())],
        "scheme": "https", "server": ("app.example", 443),
    })


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://app.example/")


def test_crawler_detection():
    assert _is_crawler("WhatsApp/2.24.1 A") is True
    assert _is_crawler("facebookexternalhit/1.1") is True
    assert _is_crawler("Mozilla/5.0 (iPhone)") is False
    assert _is_crawler("") is False


def test_og_image_prefers_absolute_logo():
    assert _og_image({"logo": "https://cdn.example/logo.png"}, "https://app.example") == \
        "https://cdn.example/logo.png"


def test_og_image_falls_back_to_brand_card():
    assert _og_image({"logo": ""}, "https://app.example") == "https://app.example/og-default.png"


def test_crawler_gets_open_graph_tags():
    share_router.db = FakeDB([_restaurant()])
    response = asyncio.run(share_router.share_card("rest_demo_chezawa", _request("WhatsApp/2.24")))
    body = response.body.decode()
    assert response.status_code == 200
    assert 'og:title" content="Commandez chez Chez Awa"' in body
    assert 'og:description" content="Maquis ivoirien"' in body
    assert "https://app.example/og-default.png" in body
    assert "https://app.example/s/rest_demo_chezawa" in body
    assert "https://app.example/experience/rest_demo_chezawa" in body
    assert response.headers["cache-control"] == "public, max-age=300"


def test_browser_is_redirected_with_source():
    share_router.db = FakeDB([_restaurant()])
    response = asyncio.run(share_router.share_card(
        "rest_demo_chezawa", _request("Mozilla/5.0", "src=qr")))
    assert response.status_code == 302
    assert response.headers["location"] == "https://app.example/experience/rest_demo_chezawa?src=qr"


def test_unknown_restaurant_is_404_without_leak():
    share_router.db = FakeDB([])
    response = asyncio.run(share_router.share_card("nope", _request("WhatsApp/2.24")))
    assert response.status_code == 404
    assert "Chez Awa" not in response.body.decode()


def test_suspended_restaurant_is_404():
    share_router.db = FakeDB([_restaurant(status="suspended")])
    response = asyncio.run(share_router.share_card("rest_demo_chezawa", _request("WhatsApp/2.24")))
    assert response.status_code == 404


def test_names_are_html_escaped():
    share_router.db = FakeDB([_restaurant(name="<script>alert(1)</script>")])
    response = asyncio.run(share_router.share_card("rest_demo_chezawa", _request("WhatsApp/2.24")))
    body = response.body.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_non_absolute_logo_is_not_used_in_meta():
    share_router.db = FakeDB([_restaurant(logo="/uploads/logo.png")])
    response = asyncio.run(share_router.share_card("rest_demo_chezawa", _request("WhatsApp/2.24")))
    body = response.body.decode()
    assert "https://app.example/og-default.png" in body
