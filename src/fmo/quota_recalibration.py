from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from fmo.quota_normalize import (
    CalibrationObservation,
    recompute_derived_capacities,
    refine_global_tokens_per_request,
)


@dataclass(frozen=True)
class RecalibrationResult:
    previous_factor: int
    refined_factor: int
    recomputed_capacities: dict[str, float | None]


class RecalibrationStore(Protocol):
    def transaction(self) -> AbstractContextManager[Any]: ...

    def load_calibration_observations(self, transaction: Any) -> list[CalibrationObservation]: ...

    def load_tokens_per_request(self, transaction: Any) -> int: ...

    def load_capacity_endpoints(self, transaction: Any) -> list[tuple[str, str, list[tuple[str, str, float]]]]: ...

    def persist_recalibration(
        self,
        transaction: Any,
        *,
        tokens_per_request: int,
        capacities: dict[str, float | None],
    ) -> None: ...


class TokensPerRequestRecalibrator:
    def __init__(
        self,
        store: RecalibrationStore,
        *,
        min_total_requests: int = 100,
        max_change_ratio: float = 0.5,
    ):
        self.store = store
        self.min_total_requests = min_total_requests
        self.max_change_ratio = max_change_ratio

    def run(self) -> RecalibrationResult:
        with self.store.transaction() as transaction:
            observations = self.store.load_calibration_observations(transaction)
            current = self.store.load_tokens_per_request(transaction)
            refined = refine_global_tokens_per_request(
                observations,
                current=current,
                min_total_requests=self.min_total_requests,
                max_change_ratio=self.max_change_ratio,
            )
            capacities = recompute_derived_capacities(
                self.store.load_capacity_endpoints(transaction),
                tokens_per_request=refined,
            )
            self.store.persist_recalibration(
                transaction,
                tokens_per_request=refined,
                capacities=capacities,
            )
        return RecalibrationResult(
            previous_factor=current,
            refined_factor=refined,
            recomputed_capacities=capacities,
        )
