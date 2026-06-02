from datetime import datetime, timedelta, timezone


def check_open(opening_hours_str: str | None, client_utc_offset: int = 0) -> bool | None:
    """Return True/False if opening_hours data is available, None otherwise.

    client_utc_offset: minutes east of UTC (e.g. 180 for Moscow UTC+3).
    Uses naive local datetime so opening_hours-py doesn't need a named timezone.
    """
    if not opening_hours_str:
        return None
    try:
        from opening_hours import OpeningHours  # Rust-backed, lazy import

        local_now = (datetime.now(timezone.utc) + timedelta(minutes=client_utc_offset)).replace(
            tzinfo=None
        )
        return OpeningHours(opening_hours_str).is_open(local_now)
    except Exception:
        return None
