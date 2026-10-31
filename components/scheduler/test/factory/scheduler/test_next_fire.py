from datetime import datetime, timezone

import pytest

from factory.scheduler.runtime.models import ScheduleKind
from factory.scheduler.runtime.next_fire import next_fire


def test_cron_uses_iana_timezone_and_skips_local_dates() -> None:
    base = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    value = next_fire(
        ScheduleKind.CRON, created_at=base,
        cron_expression="0 9 * * *", timezone_name="America/Chicago",
        skip_dates=("2026-09-10", "2026-09-11"),
    )
    assert value == datetime(2026, 9, 12, 14, tzinfo=timezone.utc)


def test_skip_dates_apply_to_interval_and_one_shot() -> None:
    base = datetime(2026, 9, 11, 1, tzinfo=timezone.utc)
    interval = next_fire(
        ScheduleKind.INTERVAL, created_at=base, interval_seconds=3600,
        timezone_name="UTC", skip_dates=("2026-09-11",),
    )
    assert interval == datetime(2026, 9, 12, 0, tzinfo=timezone.utc)
    one_shot = next_fire(
        ScheduleKind.ONE_SHOT, created_at=base,
        one_shot_at=base, skip_dates=("2026-09-11",),
    )
    assert one_shot is None


@pytest.mark.parametrize("value", ["2026-9-1", "not-a-date", "2026-02-30"])
def test_skip_dates_are_strict(value: str) -> None:
    with pytest.raises(ValueError):
        next_fire(
            ScheduleKind.INTERVAL,
            created_at=datetime.now(timezone.utc), interval_seconds=60,
            skip_dates=(value,),
        )


def test_cron_requires_valid_five_field_expression() -> None:
    with pytest.raises(ValueError, match="five-field"):
        next_fire(
            ScheduleKind.CRON, created_at=datetime.now(timezone.utc),
            cron_expression="bad cron",
        )
