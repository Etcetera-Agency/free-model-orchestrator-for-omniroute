import argparse
from collections.abc import Callable
from dataclasses import dataclass

from fmo.external_metadata import ExternalMetadataError
from fmo.metadata_sync import sync_external_metadata


COMMANDS = [
    "sync-free-registry",
    "discover-accounts",
    "scan-providers",
    "research-quotas",
    "classify-access",
    "sync-metadata",
    "match-models",
    "probe-models",
    "sync-telemetry",
    "sync-quotas",
    "score-roles",
    "allocate",
    "diff",
    "apply",
    "rollback",
    "full",
    "explain-endpoint",
    "explain-role",
]

EXIT_CODES = {
    "success": 0,
    "partial_stale": 2,
    "validation_failed": 3,
    "external_dependency_failed": 4,
    "unsafe_to_apply": 5,
    "apply_failed_rolled_back": 6,
    "rollback_failed": 7,
}


@dataclass(frozen=True)
class CliResult:
    exit_code: int
    changed: bool
    combo_test_called: bool = False
    error_reason: str | None = None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="free-model-orchestrator")
    _add_common_flags(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        _add_common_flags(subparsers.add_parser(command))
    aa = subparsers.add_parser("aa-index")
    aa.add_argument("aa_command", choices=["status", "analyze", "proposal", "approve", "reject", "rollout", "rollback"])
    _add_common_flags(aa)
    return parser.parse_args(argv)


def run_cli(argv: list[str], *, preconditions_ok: bool, metadata_sync: Callable[..., object] | None = None) -> CliResult:
    args = parse_args(argv)
    if args.command == "apply" and not preconditions_ok:
        return CliResult(exit_code=EXIT_CODES["unsafe_to_apply"], changed=False)
    if args.command in {"sync-metadata", "full"}:
        sync = metadata_sync or sync_external_metadata
        try:
            sync(dry_run=args.dry_run)
        except ExternalMetadataError as exc:
            return CliResult(exit_code=EXIT_CODES["external_dependency_failed"], changed=False, error_reason=exc.reason)
    if args.dry_run:
        return CliResult(exit_code=EXIT_CODES["success"], changed=False, combo_test_called=False)
    return CliResult(exit_code=EXIT_CODES["success"], changed=args.command == "apply")


def main() -> int:
    return run_cli([], preconditions_ok=True).exit_code


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--account")
    parser.add_argument("--endpoint")
    parser.add_argument("--role")
    parser.add_argument("--run-id")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
