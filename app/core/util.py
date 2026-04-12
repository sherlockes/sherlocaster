from datetime import datetime, timezone, timedelta

def recent_enough(published_str, days: int):
    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return published >= cutoff

def parse_datetime(ts: str) -> datetime:
    """
    Convierte timestamps ISO8601 a datetime con fallback a utcnow().
    """
    if not ts:
        return datetime.utcnow()

    try:
        # Maneja formatos "2024-05-11T18:42:00Z" o "+00:00"
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()
