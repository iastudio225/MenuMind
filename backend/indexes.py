"""Declarative MongoDB index specifications. Importing this module does no I/O."""
from models import ACTIVE_PENDING_REGISTRATION_STATES

# (collection, key specification, options). Application is intentionally left
# to a separately invoked, explicitly authorized operational command.
INDEX_SPECS = (
    # One live registration per normalized email across PUBLIC and ADMIN.
    ("pending_registrations", (("email_normalized", 1),), {
        "unique": True,
        "partialFilterExpression": {"state": {"$in": list(ACTIVE_PENDING_REGISTRATION_STATES)}},
    }),
    ("pending_registrations", (("cleanup_at", 1),), {"expireAfterSeconds": 0}),
    # Tokens are looked up by hash; TTL cleanup is asynchronous and does not
    # replace the explicit expiration check during confirmation.
    ("email_verification_tokens", (("token_hash", 1),), {"unique": True}),
    ("email_verification_tokens", (("expires_at", 1),), {"expireAfterSeconds": 0}),
    # Durable one-trial-per-email ledger.
    ("trial_eligibility", (("email_normalized", 1),), {"unique": True}),
    # Idempotent technical operations and recovery scans.
    ("license_operations", (("operation_id", 1),), {"unique": True}),
    ("license_operations", (("state", 1), ("updated_at", 1)), {}),
    ("license_operations", (("restaurant_id", 1), ("created_at", -1)), {}),
    # Efficient per-restaurant commercial history, without uniqueness.
    ("license_history", (("restaurant_id", 1), ("start_at", -1)), {}),
    ("license_history", (("restaurant_id", 1), ("end_at", 1)), {}),
    # Atomic persistent rate-limit buckets by normalized key and scope.
    ("verification_rate_limits", (("scope", 1), ("key_hash", 1)), {"unique": True}),
    ("verification_rate_limits", (("updated_at", 1),), {"expireAfterSeconds": 7200}),
    # Admin review queue for paid conversion requests.
    ("license_conversion_requests", (("state", 1), ("requested_at", 1)), {}),
    ("license_conversion_requests", (("restaurant_id", 1), ("requested_at", -1)), {}),
)
