"""Read-only manager summary assembly."""

from __future__ import annotations

from datetime import UTC, datetime

from nerve_center.persistence.summary import SummaryRepository
from nerve_center.summary.domain import SummaryCategory, SummarySnapshot


class SummaryService:
    def __init__(self, repository: SummaryRepository) -> None:
        self.repository = repository

    def snapshot(self, starts_at: datetime, ends_at: datetime) -> SummarySnapshot:
        start = _utc(starts_at)
        end = _utc(ends_at)
        if end <= start:
            raise ValueError("ends_at must be later than starts_at")
        items = tuple(self.repository.list_items(start, end))
        counts = {category.value: 0 for category in SummaryCategory}
        for item in items:
            counts[item.category.value] += 1
        return SummarySnapshot(
            starts_at=start,
            ends_at=end,
            items=items,
            counts=counts,
        )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("summary window timestamps must be timezone-aware")
    return value.astimezone(UTC)
