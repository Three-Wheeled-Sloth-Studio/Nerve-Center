"""Typed execution-host contract with a deterministic no-op adapter."""

from __future__ import annotations

from typing import Protocol

from nerve_center.code_shop.domain import CheckoutLink, ExecutionRequest, ExecutionResult


class ExecutionHost(Protocol):
    def execute(
        self,
        request: ExecutionRequest,
        checkout: CheckoutLink,
    ) -> ExecutionResult: ...


class DeterministicExecutionHost:
    """Proves admission boundaries without executing shell or external mutations."""

    def execute(
        self,
        request: ExecutionRequest,
        checkout: CheckoutLink,
    ) -> ExecutionResult:
        return ExecutionResult(
            status="simulated",
            capability=request.capability,
            idempotency_key=request.idempotency_key,
            output={
                "repository_id": request.repository_id,
                "checkout": checkout.canonical_path,
                "branch": request.branch,
                "argument_keys": sorted(request.arguments),
                "expected_output_keys": sorted(request.expected_outputs),
            },
        )
