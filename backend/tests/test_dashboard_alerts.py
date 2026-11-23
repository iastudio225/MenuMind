"""Phase D — classifieur d'alertes stock (seuil, rupture, illimité)."""
from routers.dashboard_router import _stock_value, STOCK_ALERT_THRESHOLD


def test_unlimited_stock_has_no_alert():
    assert _stock_value(None) == (None, None)


def test_out_of_stock():
    assert _stock_value(0) == (0, "out")
    assert _stock_value(-2) == (-2, "out")


def test_low_stock_under_threshold():
    assert _stock_value(1) == (1, "low")
    assert _stock_value(STOCK_ALERT_THRESHOLD) == (STOCK_ALERT_THRESHOLD, "low")


def test_healthy_stock_has_no_alert():
    assert _stock_value(STOCK_ALERT_THRESHOLD + 1) == (STOCK_ALERT_THRESHOLD + 1, None)


def test_invalid_stock_is_treated_as_out():
    assert _stock_value("abc") == (0, "out")
    assert _stock_value("3") == (3, "low")
