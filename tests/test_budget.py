import asyncio

import pytest

from nerve_center.domain.budget import (
    BudgetExceededError,
    ResourceBudget,
    ResourceBudgetTracker,
)


def test_request_budget_is_enforced() -> None:
    tracker = ResourceBudgetTracker(ResourceBudget(max_requests=2))

    tracker.consume_request(2)

    with pytest.raises(BudgetExceededError, match="requests budget"):
        tracker.consume_request()


def test_parallel_work_slot_is_usable() -> None:
    tracker = ResourceBudgetTracker(ResourceBudget(max_parallel_work=1))

    async def use_slot() -> None:
        async with tracker.work_slot():
            return None

    asyncio.run(use_slot())
