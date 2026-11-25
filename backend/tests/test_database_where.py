"""PostgreSQL adapter — query builder must emit balanced SQL.

Regression: the ``$exists`` branch produced ``(data #> '{x}' IS NULL`` with no
closing parenthesis, so ``db.menu_items.update_many({"image_url": {"$exists":
False}}, ...)`` failed at startup with ``syntax error at or near "FOR"``.
"""
from database import Collection


def _where(query):
    return Collection(None, "menu_items")._where(query)


def test_exists_condition_is_balanced():
    sql, _ = _where({"restaurant_id": "rid", "image_url": {"$exists": False}})
    assert sql.count("(") == sql.count(")")
    assert "IS NULL)" in sql


def test_exists_true_is_balanced():
    sql, _ = _where({"image_url": {"$exists": True}})
    assert sql.count("(") == sql.count(")")
    assert "IS NOT NULL)" in sql


def test_plain_and_operator_conditions_are_balanced():
    sql, args = _where({"restaurant_id": "rid", "name": "Coca"})
    assert sql.count("(") == sql.count(")")
    assert len(args) == 4  # two args per equality (exact jsonb + containment)

    sql, _ = _where({"restaurant_id": {"$ne": "rid"}})
    assert sql.count("(") == sql.count(")")
