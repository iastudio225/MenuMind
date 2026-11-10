from datetime import datetime, timezone, timedelta
import subprocess
import sys

import pytest
from pydantic import ValidationError

from indexes import INDEX_SPECS
from models import (
    ACTIVE_PENDING_REGISTRATION_STATES,
    EmailVerificationToken, LicenseHistoryEntry, LicenseOperation,
    LicensePeriod, LicenseConversionRequest, PendingRegistration,
    TrialEligibility, VerificationRateLimitCounter, VerificationRateLimits,
    normalize_email,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 1, tzinfo=UTC)


def period(**overrides):
    data = dict(plan_code="BUSINESS", license_type="TRIAL", start_at=NOW,
                end_at=NOW + timedelta(days=7), price_snapshot=0, currency="XOF")
    data.update(overrides)
    return data


def test_trial_and_paid_are_explicit_distinct_types():
    assert LicensePeriod(**period()).license_type == "TRIAL"
    assert LicensePeriod(**period(license_type="PAID", price_snapshot=30000,
                                  currency="FCFA")).license_type == "PAID"
    with pytest.raises(ValidationError):
        LicensePeriod(**period(license_type="FREE"))


@pytest.mark.parametrize("value, expected", [
    ("  Alice.Example+promo@Example.COM  ", "alice.example+promo@example.com"),
    ("ALICE@example.com", "alice@example.com"),
])
def test_email_normalization_preserves_dots_and_plus(value, expected):
    assert normalize_email(value) == expected


@pytest.mark.parametrize("email", [" Alice@example.com", "alice@example.com ",
                                    "ALICE@example.com", "alice..x@example.com"])
def test_email_normalized_fields_reject_un_normalized_or_invalid_values(email):
    with pytest.raises(ValidationError):
        PendingRegistration(origin="PUBLIC", email_normalized=email,
                            created_at=NOW, expires_at=NOW + timedelta(days=7),
                            cleanup_at=NOW + timedelta(days=7))
    with pytest.raises(ValidationError):
        TrialEligibility(email_normalized=email, state="RESERVED", operation_id="op1",
                         reserved_at=NOW)


def test_normalized_email_fields_accept_normalized_address():
    assert PendingRegistration(origin="PUBLIC", email_normalized="alice.x+tag@example.com",
                               created_at=NOW, expires_at=NOW + timedelta(days=7),
                               cleanup_at=NOW + timedelta(days=7)).email_normalized == "alice.x+tag@example.com"
    assert TrialEligibility(email_normalized="alice.x+tag@example.com", state="RESERVED",
                            operation_id="op1", reserved_at=NOW).email_normalized == "alice.x+tag@example.com"


def test_verification_limit_defaults():
    limits = VerificationRateLimits()
    assert limits.model_dump() == {
        "link_validity_hours": 24,
        "resend_cooldown_seconds": 60,
        "email_requests_per_hour": 5,
        "ip_requests_per_hour": 20,
    }
    assert VerificationRateLimits(ip_requests_per_hour=12).ip_requests_per_hour == 12


def test_pending_registration_origin_contract():
    public = PendingRegistration(origin="PUBLIC", email_normalized="a@example.com",
                                created_at=NOW, expires_at=NOW + timedelta(days=7),
                                cleanup_at=NOW + timedelta(days=7))
    assert public.created_by_admin_id is None
    admin = PendingRegistration(origin="ADMIN", email_normalized="b@example.com",
                                created_by_admin_id="admin-1", created_at=NOW,
                                expires_at=NOW + timedelta(days=7),
                                cleanup_at=NOW + timedelta(days=7))
    assert admin.created_by_admin_id == "admin-1"
    with pytest.raises(ValidationError):
        PendingRegistration(origin="ADMIN", email_normalized="b@example.com",
                            created_at=NOW, expires_at=NOW + timedelta(days=7),
                            cleanup_at=NOW + timedelta(days=7))
    with pytest.raises(ValidationError):
        PendingRegistration(origin="PUBLIC", email_normalized="b@example.com",
                            created_by_admin_id="admin-1", created_at=NOW,
                            expires_at=NOW + timedelta(days=7),
                            cleanup_at=NOW + timedelta(days=7))


def test_all_contracts_reject_invalid_states():
    with pytest.raises(ValidationError):
        LicenseOperation(operation_id="op-1", operation_type="CREATE", state="MYSTERY",
                         created_at=NOW, updated_at=NOW)
    with pytest.raises(ValidationError):
        EmailVerificationToken(token_hash="hash", pending_registration_id="p1", generation=1,
                              state="MYSTERY", created_at=NOW, expires_at=NOW + timedelta(hours=24))
    with pytest.raises(ValidationError):
        LicenseConversionRequest(request_id="c1", restaurant_id="r1", requested_plan_code="PRO",
                                 state="MYSTERY", requested_by="u1", requested_at=NOW)


def test_all_datetime_contracts_reject_naive_values_and_incoherent_order():
    naive = datetime(2026, 11, 1)
    naive_iso = "2026-11-01T00:00:00"
    with pytest.raises(ValidationError):
        LicenseOperation(operation_id="op1", operation_type="CREATE", created_at=naive, updated_at=NOW)
    with pytest.raises(ValidationError):
        PendingRegistration(origin="PUBLIC", email_normalized="a@example.com", created_at=naive,
                            expires_at=NOW + timedelta(days=1), cleanup_at=NOW + timedelta(days=1))
    with pytest.raises(ValidationError):
        EmailVerificationToken(token_hash="h", pending_registration_id="p", generation=1,
                              created_at=NOW, expires_at=NOW + timedelta(hours=1), used_at=naive)
    with pytest.raises(ValidationError):
        VerificationRateLimitCounter(key_hash="k", scope="IP", window_started_at=NOW,
                                     request_timestamps=[naive], updated_at=NOW)
    with pytest.raises(ValidationError):
        TrialEligibility(email_normalized="a@example.com", state="RESERVED", operation_id="op",
                         reserved_at=naive)
    with pytest.raises(ValidationError):
        LicenseConversionRequest(request_id="c", restaurant_id="r", requested_plan_code="PRO",
                                 requested_by="u", requested_at=naive)
    with pytest.raises(ValidationError):
        EmailVerificationToken(token_hash="h", pending_registration_id="p", generation=1,
                              created_at=naive_iso, expires_at=NOW + timedelta(hours=1))
    with pytest.raises(ValidationError):
        LicenseOperation(operation_id="op1", operation_type="CREATE", created_at=NOW,
                         updated_at=NOW - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        PendingRegistration(origin="PUBLIC", email_normalized="a@example.com", created_at=NOW,
                            expires_at=NOW, cleanup_at=NOW)


def test_token_state_and_usage_timestamp_must_agree():
    args = dict(token_hash="h", pending_registration_id="p", generation=1,
                created_at=NOW, expires_at=NOW + timedelta(hours=24))
    with pytest.raises(ValidationError):
        EmailVerificationToken(**args, state="USED")
    with pytest.raises(ValidationError):
        EmailVerificationToken(**args, state="ACTIVE", used_at=NOW)
    with pytest.raises(ValidationError):
        EmailVerificationToken(**args, state="USED", used_at=NOW + timedelta(days=1))


def test_pending_finalized_requires_verified_email_and_references():
    base = dict(origin="PUBLIC", email_normalized="a@example.com", state="FINALIZED",
                created_at=NOW, expires_at=NOW + timedelta(days=7), email_verified_at=NOW)
    with pytest.raises(ValidationError):
        PendingRegistration(**base)
    assert PendingRegistration(**base, user_id="u1", restaurant_id="r1").state == "FINALIZED"


def test_pending_registration_cleanup_dates_match_lifecycle_state():
    base = dict(origin="PUBLIC", email_normalized="a@example.com",
                created_at=NOW, expires_at=NOW + timedelta(days=7))
    pending = PendingRegistration(**base, cleanup_at=NOW + timedelta(days=7))
    assert pending.cleanup_at == pending.expires_at
    verified = PendingRegistration(**base, state="VERIFIED", email_verified_at=NOW)
    finalizing = PendingRegistration(**base, state="FINALIZING", email_verified_at=NOW)
    failed = PendingRegistration(**base, state="FAILED_RETRYABLE", email_verified_at=NOW)
    assert verified.cleanup_at is finalizing.cleanup_at is failed.cleanup_at is None
    finalized = PendingRegistration(**base, state="FINALIZED", email_verified_at=NOW,
                                    user_id="u1", restaurant_id="r1")
    assert finalized.cleanup_at is None
    expired = PendingRegistration(**base, state="EXPIRED", cleanup_at=NOW + timedelta(days=7))
    assert expired.state == "EXPIRED"
    with pytest.raises(ValidationError):
        PendingRegistration(**base)
    with pytest.raises(ValidationError):
        PendingRegistration(**base, cleanup_at=NOW + timedelta(days=6))
    with pytest.raises(ValidationError):
        PendingRegistration(**base, state="FINALIZED", email_verified_at=NOW,
                            user_id="u1", restaurant_id="r1", cleanup_at=NOW + timedelta(days=7))


def test_trial_consumption_and_conversion_decisions_require_references_and_dates():
    with pytest.raises(ValidationError):
        TrialEligibility(email_normalized="a@example.com", state="RESERVED", operation_id="op",
                         reserved_at=NOW, restaurant_id="r1")
    with pytest.raises(ValidationError):
        TrialEligibility(email_normalized="a@example.com", state="RESERVED", operation_id="op",
                         reserved_at=NOW, history_entry_id="h1")
    with pytest.raises(ValidationError):
        TrialEligibility(email_normalized="a@example.com", state="CONSUMED", operation_id="op",
                         reserved_at=NOW)
    assert TrialEligibility(email_normalized="a@example.com", state="CONSUMED", operation_id="op",
                           reserved_at=NOW, consumed_at=NOW, restaurant_id="r1",
                           history_entry_id="h1").state == "CONSUMED"
    base = dict(request_id="c1", restaurant_id="r1", requested_plan_code="PRO", requested_by="u1",
                requested_at=NOW)
    with pytest.raises(ValidationError):
        LicenseConversionRequest(**base, state="APPROVED")
    with pytest.raises(ValidationError):
        LicenseConversionRequest(**base, state="PENDING", decided_by="admin", decided_at=NOW)
    assert LicenseConversionRequest(**base, state="REJECTED", decided_by="admin",
                                    decided_at=NOW).state == "REJECTED"


def test_supporting_persistence_contracts_accept_valid_documents():
    token = EmailVerificationToken(token_hash="hash", pending_registration_id="p1", generation=1,
                                   created_at=NOW, expires_at=NOW + timedelta(hours=24))
    counter = VerificationRateLimitCounter(key_hash="key-hash", scope="EMAIL",
                                           window_started_at=NOW, updated_at=NOW)
    eligibility = TrialEligibility(email_normalized="a@example.com", state="RESERVED",
                                   operation_id="op-1", reserved_at=NOW)
    assert token.state == "ACTIVE" and counter.scope == "EMAIL" and eligibility.state == "RESERVED"


def test_index_declarations_match_contract_fields_and_uniqueness():
    indexes = {(collection, keys): options for collection, keys, options in INDEX_SPECS}
    assert indexes[("pending_registrations", (("email_normalized", 1),))]["unique"] is True
    active = indexes[("pending_registrations", (("email_normalized", 1),))]["partialFilterExpression"]
    assert set(active["state"]["$in"]) == set(ACTIVE_PENDING_REGISTRATION_STATES)
    assert set(ACTIVE_PENDING_REGISTRATION_STATES) == {
        "PENDING_VERIFICATION", "VERIFIED", "FINALIZING", "FAILED_RETRYABLE",
    }
    assert indexes[("trial_eligibility", (("email_normalized", 1),))]["unique"] is True
    assert indexes[("email_verification_tokens", (("token_hash", 1),))]["unique"] is True
    assert indexes[("license_operations", (("operation_id", 1),))]["unique"] is True
    assert ("license_history", (("restaurant_id", 1), ("start_at", -1))) in indexes
    assert all(not options.get("unique") for collection, _, options in INDEX_SPECS
               if collection == "license_history")
    assert not any(options.get("expireAfterSeconds") is not None
                   for collection, _, options in INDEX_SPECS
                   if collection in {"trial_eligibility", "license_history"})
    pending_ttl = next((keys, options) for collection, keys, options in INDEX_SPECS
                       if collection == "pending_registrations" and options.get("expireAfterSeconds") is not None)
    assert pending_ttl[0] == (("cleanup_at", 1),)
    assert ("expires_at", 1) not in pending_ttl[0]
    assert VerificationRateLimitCounter.model_fields.keys() >= {"scope", "key_hash", "request_timestamps"}
    assert LicenseHistoryEntry.model_fields.keys() >= {"license_type", "restaurant_id", "start_at", "end_at"}


def test_importing_contracts_and_indexes_does_not_load_mongo_driver():
    code = (
        "import sys; import models, indexes; "
        "assert 'motor.motor_asyncio' not in sys.modules; "
        "assert not any(hasattr(indexes, name) for name in ('apply_indexes', 'ensure_indexes'))"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_every_datetime_field_rejects_naive_values():
    naive = datetime(2026, 11, 1)
    future = NOW + timedelta(days=7)
    factories = [
        (LicensePeriod, period(), ("start_at", "end_at")),
        (LicenseHistoryEntry, dict(**period(), restaurant_id="r1", action="CREATE",
                                   created_by="u1", created_at=NOW), ("start_at", "end_at", "created_at")),
        (LicenseOperation, dict(operation_id="o", operation_type="CREATE", created_at=NOW,
                                updated_at=NOW), ("created_at", "updated_at")),
        (PendingRegistration, dict(origin="PUBLIC", email_normalized="a@example.com",
                                   created_at=NOW, expires_at=future, cleanup_at=future),
         ("created_at", "expires_at", "cleanup_at", "email_verified_at")),
        (EmailVerificationToken, dict(token_hash="h", pending_registration_id="p", generation=1,
                                      created_at=NOW, expires_at=future), ("created_at", "expires_at", "used_at")),
        (VerificationRateLimitCounter, dict(key_hash="k", scope="IP", window_started_at=NOW,
                                            request_timestamps=[NOW], updated_at=NOW),
         ("window_started_at", "updated_at", "request_timestamps")),
        (TrialEligibility, dict(email_normalized="a@example.com", state="RESERVED",
                                operation_id="o", reserved_at=NOW), ("reserved_at", "consumed_at")),
        (LicenseConversionRequest, dict(request_id="c", restaurant_id="r", requested_plan_code="PRO",
                                        requested_by="u", requested_at=NOW),
         ("requested_at", "decided_at")),
    ]
    for model, data, fields in factories:
        for field in fields:
            invalid = dict(data)
            if field == "request_timestamps":
                invalid[field] = [naive]
            else:
                invalid[field] = naive
            with pytest.raises(ValidationError, match=".+"):
                model(**invalid)
