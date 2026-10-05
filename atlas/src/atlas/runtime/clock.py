"""Injectable clocks. Engines never call ``datetime.now()`` directly."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Protocol

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


class Clock(Protocol):
    def now_utc(self) -> datetime: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Deterministic clock for tests and replay."""

    def __init__(self, at: datetime):
        if at.tzinfo is None:
            raise ValueError("FixedClock requires an aware datetime")
        self._at = at.astimezone(timezone.utc)

    def now_utc(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = at.astimezone(timezone.utc)

    def advance(self, **kwargs: float) -> None:
        self._at = self._at + timedelta(**kwargs)


def trading_day(ts: datetime, offset_minutes: int = 330) -> date:
    """Calendar trading day in exchange local time (IST by default)."""
    tz = timezone(timedelta(minutes=offset_minutes))
    return ts.astimezone(tz).date()
