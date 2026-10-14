"""D1.25 — retention purge of old AI conversations (mocked DB, no real data).

Confirms: only conversations older than the cutoff are removed, dry_run never
deletes, orders are never touched, recent chats are kept.
"""
from types import SimpleNamespace

import pytest

from services.ai import retention


class _Col:
    def __init__(self, docs):
        self.docs = docs

    def _match(self, d, q):
        cond = q.get("updated_at")
        if isinstance(cond, dict) and "$lt" in cond:
            v = d.get("updated_at")
            return v is not None and v < cond["$lt"]
        return all(d.get(k) == v for k, v in q.items())

    async def count_documents(self, q):
        return len([d for d in self.docs if self._match(d, q)])

    async def delete_many(self, q):
        keep, dead = [], []
        for d in self.docs:
            (dead if self._match(d, q) else keep).append(d)
        self.docs = keep
        return SimpleNamespace(deleted_count=len(dead))


class FakeDB:
    def __init__(self, docs):
        self.ai_conversations = _Col(list(docs))
        self.orders = _Col([{"_id": "o1", "reference": "CMD-1"}])


def _iso(days_ago: float) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _docs():
    return [
        {"conversation_id": "old-plain", "updated_at": _iso(120)},
        {"conversation_id": "old-with-order", "updated_at": _iso(120),
         "order_reference": "CMD-1"},
        {"conversation_id": "recent", "updated_at": _iso(5)},
        {"conversation_id": "no-date"},
    ]


def test_purge_removes_only_older_than_cutoff():
    db = FakeDB(_docs())
    res = _run_retention(db, dry_run=False)
    assert res["matched"] == 2
    assert res["deleted"] == 2
    left = {d["conversation_id"] for d in db.ai_conversations.docs}
    assert left == {"recent", "no-date"}  # recent + undated kept


def test_dry_run_counts_but_never_deletes():
    db = FakeDB(_docs())
    res = _run_retention(db, dry_run=True)
    assert res["matched"] == 2 and res["deleted"] == 0
    assert len(db.ai_conversations.docs) == 4


def test_orders_never_touched():
    db = FakeDB(_docs())
    _run_retention(db, dry_run=False)
    assert db.orders.docs == [{"_id": "o1", "reference": "CMD-1"}]


def test_invalid_days_rejected():
    with pytest.raises(ValueError):
        _run_retention(FakeDB([]), days=0)


# ---- CLI guard (main): confirmation before any real deletion ----
class TestCliGuard:
    def _main(self, monkeypatch, argv, answer=None):
        calls = []

        async def fake_purge(**kw):
            calls.append(kw)
            return {"matched": 0, "deleted": 0, "cutoff": "", "dry_run": kw.get("dry_run")}

        monkeypatch.setattr(retention, "purge_old_conversations", fake_purge)
        monkeypatch.setattr("sys.argv", ["retention"] + argv)
        if answer is None:
            def boom(*a, **k):
                raise AssertionError("input() must not be called")
            monkeypatch.setattr("builtins.input", boom)
        else:
            monkeypatch.setattr("builtins.input", lambda *_: answer)
        retention.main()
        return calls

    def test_real_purge_cancelled_without_oui(self, monkeypatch):
        calls = self._main(monkeypatch, ["--days", "90"], answer="non")
        assert calls == []  # cancelled: purge never invoked

    def test_real_purge_runs_after_oui(self, monkeypatch):
        calls = self._main(monkeypatch, ["--days", "90"], answer="oui")
        assert calls == [{"older_than_days": 90, "dry_run": False}]

    def test_yes_flag_skips_input(self, monkeypatch):
        calls = self._main(monkeypatch, ["--yes"])  # input would raise
        assert calls == [{"older_than_days": 90, "dry_run": False}]

    def test_dry_run_never_asks(self, monkeypatch):
        calls = self._main(monkeypatch, ["--dry-run"])  # input would raise
        assert calls == [{"older_than_days": 90, "dry_run": True}]


def _run_retention(db, dry_run=False, days=90):
    import asyncio
    return asyncio.run(retention.purge_old_conversations(
        db=db, older_than_days=days, dry_run=dry_run))
