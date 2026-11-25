"""Lot C — public link attribution: sources, dedupe, rate limiting."""
import asyncio

import pytest
from fastapi import HTTPException

from routers import public_events_router as events
from services.attribution import normalize_source


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def insert_one(self, doc):
        self.docs.append(doc)


class FakeDB:
    def __init__(self, restaurants):
        self.restaurants = FakeCollection(restaurants)
        self.public_events = FakeCollection()


def _restaurant(public_id="rest_demo_chezawa", status="active"):
    return {"_id": "rid-1", "public_id": public_id, "status": status}


def _body(**overrides):
    payload = {"public_id": "rest_demo_chezawa", "kind": "visit",
               "source": "wa", "session_id": "session-1234"}
    payload.update(overrides)
    return events.PublicEventBody(**payload)


@pytest.fixture(autouse=True)
def _reset_limits():
    events.reset_rate_limits()
    yield
    events.reset_rate_limits()


# ---------- source normalization ----------

@pytest.mark.parametrize("raw,expected", [
    ("wa", "wa"),
    ("WA", "wa"),
    (" qr ", "qr"),
    ("instagram", "other"),
    ("", "direct"),
    (None, "direct"),
    ("x" * 40, "other"),
])
def test_normalize_source(raw, expected):
    assert normalize_source(raw) == expected


def test_normalize_source_bounds_length():
    assert len(normalize_source("a" * 200)) <= 16


# ---------- endpoint ----------

def test_records_first_visit_then_dedupes():
    events.db = FakeDB([_restaurant()])
    first = asyncio.run(events.record_event(_body()))
    second = asyncio.run(events.record_event(_body()))
    assert first == {"recorded": True}
    assert second == {"recorded": False}
    assert len(events.db.public_events.docs) == 1


def test_stores_normalized_source():
    events.db = FakeDB([_restaurant()])
    asyncio.run(events.record_event(_body(source="WHATSAPP")))
    stored = events.db.public_events.docs[0]
    assert stored["source"] == "other"
    assert stored["restaurant_id"] == "rid-1"
    assert stored["kind"] == "visit"


def test_unknown_restaurant_is_404():
    events.db = FakeDB([])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(events.record_event(_body()))
    assert exc.value.status_code == 404


def test_suspended_restaurant_is_404():
    events.db = FakeDB([_restaurant(status="suspended")])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(events.record_event(_body()))
    assert exc.value.status_code == 404


def test_session_id_validation():
    with pytest.raises(ValueError):
        _body(session_id="short")
    with pytest.raises(ValueError):
        _body(session_id="bad id with spaces")


def test_rate_limit_allows_five_events_per_minute():
    for _ in range(events.MAX_EVENTS_PER_MINUTE):
        assert events._allow("session-1234") is True
    assert events._allow("session-1234") is False
    assert events._allow("other-session") is True


def test_duplicate_visit_does_not_consume_rate_limit():
    events.db = FakeDB([_restaurant()])
    asyncio.run(events.record_event(_body()))
    for _ in range(events.MAX_EVENTS_PER_MINUTE + 1):
        asyncio.run(events.record_event(_body()))
    assert len(events.db.public_events.docs) == 1
