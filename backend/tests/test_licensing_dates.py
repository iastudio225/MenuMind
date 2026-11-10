from datetime import date, datetime, timezone, timedelta
import os
import subprocess
import sys
import time

import pytest

from services.licensing_dates import (
    add_calendar_months, calculate_status, civil_date_to_utc, monthly_expiry,
    validate_period,
)

UTC = timezone.utc


@pytest.mark.parametrize(("plan", "start", "end", "now", "expected"), [
    (None, None, None, datetime(2026, 1, 1, tzinfo=UTC), "UNASSIGNED"),
    ("STARTER", None, None, datetime(2026, 1, 1, tzinfo=UTC), "DATA_INCOMPLETE"),
    ("STARTER", "bad", "2026-02-01", datetime(2026, 1, 1, tzinfo=UTC), "DATA_INCOMPLETE"),
    ("STARTER", "2026-02-01", "2026-03-01", datetime(2026, 1, 1, tzinfo=UTC), "NOT_STARTED"),
    ("STARTER", "2026-01-01", "2026-02-01", datetime(2026, 1, 15, tzinfo=UTC), "ACTIVE"),
    ("STARTER", "2026-01-01", "2026-02-01", datetime(2026, 2, 1, tzinfo=UTC), "EXPIRED"),
    ("STARTER", "2026-02-01", "2026-01-01", datetime(2026, 1, 15, tzinfo=UTC), "DATA_INCOMPLETE"),
])
def test_statuses(plan, start, end, now, expected):
    assert calculate_status(plan, start, end, now) == expected


def test_strict_civil_date_and_abidjan_utc_conversion():
    assert civil_date_to_utc("2026-10-10") == datetime(2026, 10, 10, tzinfo=UTC)
    for value in ("2026-1-01", "2026-02-30", "2026-10-10T00:00:00"):
        with pytest.raises(ValueError):
            civil_date_to_utc(value)


@pytest.mark.parametrize(("start", "expected"), [
    (date(2025,  1, 28), date(2025, 2, 28)),
    (date(2025,  1, 29), date(2025, 2, 28)),
    (date(2025,  1, 30), date(2025, 2, 28)),
    (date(2025, 1, 31), date(2025, 2, 28)),
    (date(2024, 1, 28), date(2024, 2, 28)),
    (date(2024, 1, 29), date(2024, 2, 29)),
    (date(2024, 1, 30), date(2024, 2, 29)),
    (date(2024, 1, 31), date(2024, 2, 29)),
    (date(2025, 3, 28), date(2025, 4, 28)),
    (date(2025, 3, 29), date(2025, 4, 29)),
    (date(2025, 3, 30), date(2025, 4, 30)),
    (date(2025, 3, 31), date(2025, 4, 30)),
    (date(2024, 2, 29), date(2024, 3, 29)),
    (date(2026, 3, 31), date(2026, 4, 30)),
    (date(2026, 10, 10), date(2026, 11, 10)),
])
def test_monthly_expiry(start, expected):
    assert monthly_expiry(start) == expected


def test_months_are_calculated_from_original_start_without_drift():
    start = date(2025, 1, 31)
    assert add_calendar_months(start, 2) == date(2025, 3, 31)
    assert add_calendar_months(start, 1) == date(2025, 2, 28)
    assert add_calendar_months(start, 2) == date(2025, 3, 31)
    assert add_calendar_months(start, 3) == date(2025, 4, 30)


def test_period_validation_and_half_open_boundary():
    start, end = civil_date_to_utc("2026-10-10"), civil_date_to_utc("2026-11-10")
    validate_period(start, end)
    assert calculate_status("STARTER", start, end, end - timedelta(microseconds=1)) == "ACTIVE"
    assert calculate_status("STARTER", start, end, end) == "EXPIRED"
    with pytest.raises(ValueError):
        validate_period(end, start)


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        calculate_status("STARTER", "2026-01-01", "2026-02-01", datetime(2026, 1, 15))
def test_civil_conversion_is_independent_of_host_timezone():
    if hasattr(time, "tzset"):
        # Change TZ only in isolated child processes; the test runner's clock
        # and process-wide timezone configuration are never modified.
        code = (
            "import time; time.tzset(); "
            "from datetime import datetime, timezone; "
            "from services.licensing_dates import civil_date_to_utc; "
            "print(datetime(2026,10,10,tzinfo=timezone.utc).astimezone().isoformat()+'|'+"
            "civil_date_to_utc('2026-10-10').isoformat())"
        )
        outputs = []
        for zone in ("Pacific/Honolulu", "Asia/Tokyo"):
            env = os.environ.copy()
            env["TZ"] = zone
            outputs.append(subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip())
        local_times = [output.split("|")[0] for output in outputs]
        contract_times = [output.split("|")[1] for output in outputs]
        assert local_times[0] != local_times[1]
        assert contract_times == ["2026-10-10T00:00:00+00:00"] * 2
    else:
        # Windows has no time.tzset(): compare equivalent aware instants with
        # distinct offsets, then verify civil input still uses Abidjan.
        from zoneinfo import ZoneInfo

        instant_utc = datetime(2026, 10, 10, 0, tzinfo=UTC)
        instant_plus_five = datetime(2026, 10, 10, 5, tzinfo=ZoneInfo("Asia/Karachi"))
        assert instant_utc.astimezone(UTC) == instant_plus_five.astimezone(UTC)
        start = datetime(2026, 10, 9, 0, tzinfo=UTC)
        end = datetime(2026, 10, 11, 0, tzinfo=UTC)
        assert calculate_status("STARTER", start, end, instant_utc) == calculate_status(
            "STARTER", start, end, instant_plus_five
        ) == "ACTIVE"
        assert civil_date_to_utc("2026-10-10") == datetime(2026, 10, 10, tzinfo=UTC)


def test_license_period_models_require_aware_ordered_datetimes_and_preserve_legacy_fields():
    from pydantic import ValidationError
    from models import AdminRestaurantUpdate, LicenseHistoryEntry, LicensePeriod

    start = datetime(2026, 10, 10, tzinfo=UTC)
    end = datetime(2026, 11, 10, tzinfo=UTC)
    period = LicensePeriod(plan_code="STARTER", license_type="PAID", start_at=start, end_at=end,
                           price_snapshot=15000, currency="FCFA")
    assert period.start_at == start and period.end_at == end
    with pytest.raises(ValidationError):
        LicensePeriod(plan_code="STARTER", license_type="PAID", start_at=start.replace(tzinfo=None), end_at=end,
                      price_snapshot=15000, currency="FCFA")
    for invalid_end in (start - timedelta(seconds=1), start):
        with pytest.raises(ValidationError):
            LicensePeriod(plan_code="STARTER", license_type="PAID", start_at=start, end_at=invalid_end,
                          price_snapshot=15000, currency="FCFA")
    history = LicenseHistoryEntry(restaurant_id="r1", plan_code="STARTER", license_type="PAID", start_at=start,
                                  end_at=end, action="CREATE", previous_plan_code=None,
                                  price_snapshot=15000, currency="FCFA", created_by="admin",
                                  created_at=start)
    assert history.action == "CREATE"
    with pytest.raises(ValidationError):
        LicenseHistoryEntry(restaurant_id="r1", plan_code="STARTER", license_type="PAID", start_at=start,
                            end_at=end, action="CREATE", price_snapshot=15000,
                            currency="FCFA", created_by="admin", created_at=datetime(2026, 10, 10))
    old = AdminRestaurantUpdate(plan="STARTER", plan_activated_at="2026-10-10",
                                plan_expires_at="2026-11-10")
    assert old.plan == "STARTER"
    assert old.plan_activated_at == "2026-10-10"
    assert old.plan_expires_at == "2026-11-10"
