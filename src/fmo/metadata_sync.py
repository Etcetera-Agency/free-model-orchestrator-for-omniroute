import os
from dataclasses import dataclass

from fmo.artificial_analysis import AASnapshot, fetch_artificial_analysis_free_snapshot
from fmo.candidates import FreeCandidate
from fmo.models_dev import sync_models_dev_candidates


@dataclass(frozen=True)
class MetadataSyncResult:
    candidates: dict[tuple[str, str], FreeCandidate]
    aa_snapshot: AASnapshot
    dry_run: bool = False


def sync_external_metadata(*, dry_run: bool = False, aa_api_key: str | None = None) -> MetadataSyncResult:
    api_key = aa_api_key or os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY") or os.environ.get("AA_API_KEY")
    candidates = sync_models_dev_candidates()
    aa_snapshot = fetch_artificial_analysis_free_snapshot(api_key=api_key)
    return MetadataSyncResult(candidates=candidates, aa_snapshot=aa_snapshot, dry_run=dry_run)
