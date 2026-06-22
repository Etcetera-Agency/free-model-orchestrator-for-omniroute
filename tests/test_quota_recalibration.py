from contextlib import contextmanager

import pytest

from fmo.quota_normalize import CalibrationObservation
from fmo.quota_recalibration import TokensPerRequestRecalibrator


class _Store:
    def __init__(self, *, observations, current=2000, endpoints=None):
        self.observations = observations
        self.current = current
        self.endpoints = endpoints or []
        self.persisted = []
        self.transactions = 0

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield {"transaction": self.transactions}

    def load_calibration_observations(self, transaction):
        return self.observations

    def load_tokens_per_request(self, transaction):
        return self.current

    def load_capacity_endpoints(self, transaction):
        return self.endpoints

    def persist_recalibration(self, transaction, *, tokens_per_request, capacities):
        self.persisted.append(
            {
                "transaction": transaction,
                "tokens_per_request": tokens_per_request,
                "capacities": capacities,
            }
        )


@pytest.mark.spec("quota-manager::Factor refined from observations")
@pytest.mark.spec("quota-manager::Derived endpoints recomputed, live untouched")
@pytest.mark.spec("quota-manager::Factor and capacities persisted consistently")
def test_weekly_recalibration_refines_factor_and_persists_derived_capacities_together():
    store = _Store(
        observations=[
            CalibrationObservation("a", 900_000, 600),
            CalibrationObservation("b", 600_000, 400),
        ],
        endpoints=[
            ("summary-endpoint", "summary", [("tokens", "day", 1_500_000)]),
            ("calibrated-endpoint", "calibrated", [("requests", "day", 800)]),
            ("live-endpoint", "live", [("tokens", "day", 1_500_000)]),
        ],
    )

    result = TokensPerRequestRecalibrator(store).run()

    assert result.previous_factor == 2000
    assert result.refined_factor == 1500
    assert result.recomputed_capacities == {
        "summary-endpoint": 1000,
        "calibrated-endpoint": 800,
    }
    assert store.transactions == 1
    assert store.persisted == [
        {
            "transaction": {"transaction": 1},
            "tokens_per_request": 1500,
            "capacities": result.recomputed_capacities,
        }
    ]
