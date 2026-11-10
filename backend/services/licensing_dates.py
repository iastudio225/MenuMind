"""Pure date and license-status rules; deliberately independent of MongoDB."""
from calendar import monthrange
from datetime import date, datetime, time, timezone
import re
from typing import Optional
from zoneinfo import ZoneInfo

CONTRACT_TZ = ZoneInfo("Africa/Abidjan")
_CIVIL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def civil_date_to_utc(value: str) -> datetime:
    """Parse strict YYYY-MM-DD as midnight in Abidjan, returned as aware UTC."""
    if not isinstance(value, str) or not _CIVIL_DATE.fullmatch(value):
        raise ValueError("Date attendue au format YYYY-MM-DD")
    try:
        local_date = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date civile invalide") from exc
    return datetime.combine(local_date, time.min, CONTRACT_TZ).astimezone(timezone.utc)


def add_calendar_months(start: date, months: int = 1) -> date:
    """Add calendar months from the original start date, clamping month end."""
    if months < 0:
        raise ValueError("Le nombre de mois doit être positif ou nul")
    index = start.year * 12 + (start.month - 1) + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def monthly_expiry(start: date) -> date:
    return add_calendar_months(start, 1)


def validate_period(start_at: datetime, end_at: datetime) -> None:
    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise ValueError("Les instants doivent inclure un fuseau horaire")
    if end_at.astimezone(timezone.utc) <= start_at.astimezone(timezone.utc):
        raise ValueError("La fin doit être postérieure au début")


def _instant(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else None
    if isinstance(value, str):
        if _CIVIL_DATE.fullmatch(value):
            try:
                return civil_date_to_utc(value)
            except ValueError:
                return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
        except ValueError:
            return None
    return None


def calculate_status(plan_code, start_at, end_at, now: Optional[datetime] = None) -> str:
    if not plan_code:
        return "UNASSIGNED"
    start, end = _instant(start_at), _instant(end_at)
    if start is None or end is None or end <= start:
        return "DATA_INCOMPLETE"
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now doit inclure un fuseau horaire")
    current = current.astimezone(timezone.utc)
    if current < start:
        return "NOT_STARTED"
    return "ACTIVE" if current < end else "EXPIRED"
