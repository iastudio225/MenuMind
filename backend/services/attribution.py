"""Public link attribution — source normalization.

The public experience can be reached from WhatsApp groups, printed QR codes,
Instagram bios, etc. Only a small whitelist of sources is persisted so neither
storage nor the dashboard SQL has to trust client input:

* a missing/blank value means a direct visit;
* an unknown value is bucketed as ``other``;
* values are lower-cased and length-bounded before comparison.
"""

SOURCES = ("wa", "qr", "ig", "fb", "web", "direct", "other")
DEFAULT_SOURCE = "direct"
MAX_SOURCE_LENGTH = 16


def normalize_source(raw) -> str:
    """Return a whitelisted source label for ``raw`` (never raises)."""
    if raw is None:
        return DEFAULT_SOURCE
    try:
        value = str(raw).strip().lower()[:MAX_SOURCE_LENGTH]
    except Exception:  # pragma: no cover - defensive, str() rarely fails
        return DEFAULT_SOURCE
    if not value:
        return DEFAULT_SOURCE
    return value if value in SOURCES else "other"
