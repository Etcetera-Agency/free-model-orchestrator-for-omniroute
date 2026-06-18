"""Live ingestion checks against the real models.dev and Artificial Analysis APIs.

Per project policy OmniRoute is replayed from fixtures, but models.dev and
Artificial Analysis are exercised live here so real response shapes and schema
drift are caught. These are opt-in: they skip cleanly when the network is
unavailable, and the AA checks skip when no key is present in ``Secrets/AA.txt``
or the ``AA_API_KEY`` / ``ARTIFICIAL_ANALYSIS_API_KEY`` environment.

Run only these with::

    .venv/bin/python -m pytest -m live
"""

import os
from pathlib import Path

import pytest

from fmo.artificial_analysis import fetch_artificial_analysis_free_snapshot
from fmo.candidates import build_free_candidates
from fmo.external_metadata import ExternalMetadataError
from fmo.models_dev import fetch_models_dev_catalog

pytestmark = pytest.mark.live

SECRETS_AA = Path(__file__).resolve().parents[2] / "Secrets" / "AA.txt"


def _aa_api_key() -> str | None:
    env = os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY") or os.environ.get("AA_API_KEY")
    if env:
        return env.strip()
    if SECRETS_AA.exists():
        token = SECRETS_AA.read_text().strip()
        if token:
            return token
    return None


def _skip_if_offline(exc: ExternalMetadataError) -> None:
    transient_http_statuses = {408, 425, 429}
    transient_http_error = exc.reason == "http_error" and (
        (exc.status_code or 0) >= 500 or exc.status_code in transient_http_statuses
    )
    if exc.reason in {"network_error"} or transient_http_error:
        pytest.skip(f"external source unavailable: {exc}")


def test_models_dev_live_catalog_yields_candidates():
    try:
        catalog = fetch_models_dev_catalog(timeout=30)
    except ExternalMetadataError as exc:
        _skip_if_offline(exc)
        raise

    providers = catalog["providers"]
    assert isinstance(providers, dict) and providers
    # Real api.json has no `providers` wrapper, so a working fetch proves the
    # top-level provider-keyed shape is normalized correctly.
    assert any("models" in provider for provider in providers.values())

    candidates = build_free_candidates(catalog)
    assert candidates, "live models.dev catalog should surface at least one free candidate"


def test_artificial_analysis_live_free_snapshot_paginates():
    api_key = _aa_api_key()
    if not api_key:
        pytest.skip("no Artificial Analysis API key available")

    try:
        snapshot = fetch_artificial_analysis_free_snapshot(api_key=api_key, timeout=30)
    except ExternalMetadataError as exc:
        _skip_if_offline(exc)
        raise

    assert snapshot.index_version
    # The free tier spans multiple pages; aggregation must exceed one page.
    assert len(snapshot.models) > 200
    assert any(model.metrics.get("intelligence_index") is not None for model in snapshot.models)
