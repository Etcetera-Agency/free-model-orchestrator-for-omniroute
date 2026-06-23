from ._base import Database, Repository
from .account import ProviderAccountRepository
from .allocation_plan import AllocationPlanRepository
from .audit import AuditRepository
from .canonical_model import CanonicalModelRepository
from .catalog import ProviderCatalogRepository
from .combo_snapshot import ComboSnapshotRepository
from .endpoint import ProviderEndpointRepository
from .external_metadata import ExternalMetadataRepository
from .lock import LockRepository
from .probe import ProbeRepository
from .provider import ProviderRepository
from .quota_rule import QuotaRuleRepository
from .registry import FreeRegistryRepository
from .role import RoleRepository
from .role_consumer import RoleConsumerRepository
from .run import RunRepository
from .score import ScoreRepository
from .snapshot import SnapshotRepository

# AICODE-NOTE: this package is the public shim; keep existing imports stable
# while repository classes move between aggregate modules.
__all__ = (
    "AllocationPlanRepository",
    "AuditRepository",
    "CanonicalModelRepository",
    "ComboSnapshotRepository",
    "Database",
    "ExternalMetadataRepository",
    "FreeRegistryRepository",
    "LockRepository",
    "ProbeRepository",
    "ProviderAccountRepository",
    "ProviderCatalogRepository",
    "ProviderEndpointRepository",
    "ProviderRepository",
    "QuotaRuleRepository",
    "Repository",
    "RoleConsumerRepository",
    "RoleRepository",
    "RunRepository",
    "ScoreRepository",
    "SnapshotRepository",
)
