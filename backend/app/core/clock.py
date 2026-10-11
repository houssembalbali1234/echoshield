from datetime import datetime, timedelta, timezone

# Marge pour absorber les petits décalages d'horloge entre machines.
CLOCK_SKEW = timedelta(seconds=30)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def immediately() -> datetime:
    """Date à utiliser pour « actif dès maintenant », robuste aux décalages d'horloge."""
    return utcnow() - CLOCK_SKEW