from datetime import UTC, datetime, timedelta

import pytest

from nerve_center.domain.run_window import DurationRunWindow, FixedRunWindow


def test_duration_window_resolves_from_run_start() -> None:
    now = datetime(2026, 8, 3, 17, 0, tzinfo=UTC)

    resolved = DurationRunWindow(timedelta(minutes=30)).resolve(now)

    assert resolved.starts_at == now
    assert resolved.ends_at == now + timedelta(minutes=30)
    assert resolved.contains(now)
    assert not resolved.contains(resolved.ends_at)


def test_remaining_is_zero_after_deadline() -> None:
    now = datetime(2026, 8, 3, 17, 0, tzinfo=UTC)
    resolved = DurationRunWindow(timedelta(minutes=5)).resolve(now)

    assert resolved.remaining(now + timedelta(minutes=10)) == timedelta(0)


def test_fixed_window_keeps_explicit_bounds() -> None:
    starts_at = datetime(2026, 8, 4, 13, 0, tzinfo=UTC)
    ends_at = datetime(2026, 8, 4, 15, 0, tzinfo=UTC)

    resolved = FixedRunWindow(starts_at, ends_at).resolve(starts_at)

    assert resolved.starts_at == starts_at
    assert resolved.ends_at == ends_at


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        DurationRunWindow(timedelta(minutes=5)).resolve(datetime(2026, 8, 3, 17, 0))


def test_non_positive_duration_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        DurationRunWindow(timedelta(0))
