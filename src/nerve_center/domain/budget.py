"""Resource-budget contracts for task execution."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from threading import Lock


class BudgetExceededError(RuntimeError):
    def __init__(self, resource: str, limit: int) -> None:
        super().__init__(f"{resource} budget of {limit} was exhausted")
        self.resource = resource
        self.limit = limit


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    max_requests: int = 500
    max_llm_calls: int = 100
    max_parallel_work: int = 3

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value < 1:
                raise ValueError(f"{name} must be at least 1")


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    requests: int = 0
    llm_calls: int = 0


class ResourceBudgetTracker:
    def __init__(
        self,
        budget: ResourceBudget,
        usage: ResourceUsage | None = None,
        on_change: Callable[[ResourceUsage], None] | None = None,
    ) -> None:
        self.budget = budget
        self._usage = usage or ResourceUsage()
        self._on_change = on_change
        self._lock = Lock()
        self._semaphore = asyncio.Semaphore(budget.max_parallel_work)

    @property
    def usage(self) -> ResourceUsage:
        with self._lock:
            return self._usage

    def consume_request(self, count: int = 1) -> ResourceUsage:
        return self._consume("requests", count, self.budget.max_requests)

    def consume_llm_call(self, count: int = 1) -> ResourceUsage:
        return self._consume("llm_calls", count, self.budget.max_llm_calls)

    @asynccontextmanager
    async def work_slot(self) -> AsyncIterator[None]:
        async with self._semaphore:
            yield

    def _consume(self, resource: str, count: int, limit: int) -> ResourceUsage:
        if count < 1:
            raise ValueError("budget consumption count must be at least 1")
        with self._lock:
            current = getattr(self._usage, resource)
            if current + count > limit:
                raise BudgetExceededError(resource, limit)
            values = asdict(self._usage)
            values[resource] = current + count
            self._usage = ResourceUsage(**values)
            usage = self._usage
        if self._on_change is not None:
            self._on_change(usage)
        return usage
