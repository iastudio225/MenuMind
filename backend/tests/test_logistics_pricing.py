"""P1 logistique — règles de prix serveur (km / poids / minimum)."""
from services.order_service import line_unit_price, _booking_issues


def test_fixed_item_keeps_historical_price():
    assert line_unit_price({"price": 2500}) == 2500
    assert line_unit_price({"price": 2500}, {}) == 2500


def test_distance_pricing_is_server_side():
    item = {"price": 0, "pricing_rules": {"base": 1000, "per_km": 500}}
    assert line_unit_price(item, {"distance_km": 3}) == 2500
    # Le client ne fournit jamais le prix : seule la distance est lue.
    assert line_unit_price(item, {"distance_km": "4"}) == 3000


def test_weight_pricing_with_minimum_floor():
    item = {"price": 0, "pricing_rules": {"per_kg": 200, "min": 1000}}
    assert line_unit_price(item, {"weight_kg": 2}) == 1000
    assert line_unit_price(item, {"weight_kg": 10}) == 2000


def test_distance_and_weight_combined():
    item = {"price": 500, "pricing_rules": {"base": 500, "per_km": 300, "per_kg": 100, "min": 0}}
    assert line_unit_price(item, {"distance_km": 2, "weight_kg": 3}) == 500 + 600 + 300


def test_missing_booking_falls_back_to_base_price():
    item = {"price": 2000, "pricing_rules": {"base": 2000, "per_km": 500}}
    assert line_unit_price(item, {}) == 2000


def test_invalid_values_never_crash():
    item = {"price": 1500, "pricing_rules": {"per_km": "abc"}}
    assert line_unit_price(item, {"distance_km": "x"}) == 1500


def test_distance_required_when_per_km_is_priced():
    item = {"name": "Course", "pricing_rules": {"per_km": 500}}
    issues = _booking_issues(item, {})
    assert any("distance" in issue for issue in issues)
    assert _booking_issues(item, {"distance_km": 2}) == []


def test_weight_required_when_per_kg_is_priced():
    item = {"name": "Colis", "pricing_rules": {"per_kg": 300}}
    issues = _booking_issues(item, {})
    assert any("poids" in issue for issue in issues)
    assert _booking_issues(item, {"weight_kg": 4}) == []


def test_no_booking_requirement_for_fixed_item():
    assert _booking_issues({"name": "Divers", "pricing_rules": {}}, {}) == []
    assert _booking_issues({"name": "Divers", "price": 1000}, {}) == []
