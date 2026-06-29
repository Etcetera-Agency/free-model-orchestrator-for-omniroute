from ._base import Database, Repository
from .account import ProviderAccountRepository
from .audit import AuditRepository
from .canonical_model import CanonicalModelRepository
from .catalog import ProviderCatalogRepository
from .endpoint import ProviderEndpointRepository
from .external_metadata import ExternalMetadataRepository
from .lock import LockRepository
from .probe import ProbeRepository
from .provider import ProviderRepository
from .published_generation import PublishedGenerationRepository
from .registry import FreeRegistryRepository
from .role import RoleRepository
from .role_consumer import RoleConsumerRepository
from .run import RunRepository
from .score import ScoreRepository
from .snapshot import SnapshotRepository

# AICODE-NOTE: this package is the public shim; keep existing imports stable
# while repository classes move between aggregate modules.
__all__ = (
    "AuditRepository",
    "CanonicalModelRepository",
    "Database",
    "ExternalMetadataRepository",
    "FreeRegistryRepository",
    "LockRepository",
    "ProbeRepository",
    "ProviderAccountRepository",
    "ProviderCatalogRepository",
    "ProviderEndpointRepository",
    "ProviderRepository",
    "PublishedGenerationRepository",
    "Repository",
    "RoleConsumerRepository",
    "RoleRepository",
    "RunRepository",
    "ScoreRepository",
    "SnapshotRepository",
)
