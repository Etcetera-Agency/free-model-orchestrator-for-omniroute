import argparse
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fmo.bootstrap import bootstrap_and_dispatch
from fmo.composition import compose_runtime
from fmo.config import StartupConfig
from fmo.external_metadata import ExternalMetadataError
from fmo.idempotency import utcnow
from fmo.metadata_sync import sync_external_metadata
from fmo.provider_sweep import format_provider_sweep_result

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
    "sync-hermes-inventory",
    "reconcile-roles",
    "score-roles",
    "forecast-demand",
    "allocate",
    "diff",
    "apply",
    "rollback",
    "full",
    "serve",
    "explain-endpoint",
    "explain-role",
    "normalize-profiles",
    "sweep-provider-models",
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
    output: str | None = None


PipelineRunner = Callable[[str, argparse.Namespace], CliResult]
DiagnosticsReader = Callable[[str, str], str]
SchedulerRunner = Callable[[str], CliResult]
AaIndexHandler = Callable[[str, argparse.Namespace], CliResult]
ProfileNormalizer = Callable[[argparse.Namespace], CliResult]
ProviderSweeper = Callable[[argparse.Namespace], object]


PIPELINE_COMMANDS = {
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
    "sync-hermes-inventory",
    "reconcile-roles",
    "score-roles",
    "forecast-demand",
    "allocate",
    "diff",
    "apply",
    "rollback",
}


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


def run_cli(
    argv: list[str],
    *,
    preconditions_ok: bool,
    metadata_sync: Callable[..., object] | None = None,
    pipeline_runner: PipelineRunner | None = None,
    diagnostics_reader: DiagnosticsReader | None = None,
    scheduler_runner: SchedulerRunner | None = None,
    aa_index_handler: AaIndexHandler | None = None,
    profile_normalizer: ProfileNormalizer | None = None,
    provider_sweeper: ProviderSweeper | None = None,
) -> CliResult:
    args = parse_args(argv)
    if args.command == "aa-index":
        return _run_aa_index(args, aa_index_handler)
    if args.command == "normalize-profiles":
        return _run_profile_normalization(args, profile_normalizer)
    if args.command == "sweep-provider-models":
        return _run_provider_sweep(args, provider_sweeper)
    if args.command == "apply" and not preconditions_ok:
        return CliResult(exit_code=EXIT_CODES["unsafe_to_apply"], changed=False)
    if args.command == "serve":
        return _run_scheduler(args, scheduler_runner)
    if args.command in {"explain-endpoint", "explain-role"}:
        return _run_diagnostics(args, diagnostics_reader)
    if pipeline_runner is None and args.command in {"sync-metadata", "full"}:
        sync = metadata_sync or sync_external_metadata
        try:
            sync(dry_run=args.dry_run)
        except ExternalMetadataError as exc:
            return CliResult(exit_code=EXIT_CODES["external_dependency_failed"], changed=False, error_reason=exc.reason)
        if args.command == "sync-metadata":
            return CliResult(exit_code=EXIT_CODES["success"], changed=False)
    if args.command in PIPELINE_COMMANDS or args.command == "full":
        if pipeline_runner is None:
            return CliResult(exit_code=EXIT_CODES["success"], changed=False)
        return pipeline_runner(args.command, args)
    return CliResult(exit_code=EXIT_CODES["success"], changed=False)


def main(
    argv: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
    health_check: Callable[[], dict] | None = None,
    dispatcher: Callable[..., int] | None = None,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    run = dispatcher or _dispatch_cli
    return bootstrap_and_dispatch(args, env=env or os.environ, health_check=health_check, dispatcher=run)


def _dispatch_cli(argv: list[str], preconditions_ok: bool, config: StartupConfig) -> int:
    runtime = compose_runtime(config)
    result = run_cli(
        argv,
        preconditions_ok=preconditions_ok,
        pipeline_runner=cast(PipelineRunner, runtime.run_command),
        diagnostics_reader=runtime.read_diagnostics,
        scheduler_runner=cast(SchedulerRunner, runtime.run_scheduler_once),
        aa_index_handler=cast(AaIndexHandler, runtime.run_aa_index),
        profile_normalizer=cast(ProfileNormalizer, runtime.normalize_profiles),
        provider_sweeper=runtime.sweep_provider_models,
    )
    if result.output:
        print(result.output)
    return result.exit_code


def _run_aa_index(args: argparse.Namespace, handler: AaIndexHandler | None) -> CliResult:
    if handler is None:
        return CliResult(
            exit_code=EXIT_CODES["validation_failed"], changed=False, error_reason="aa_index_handler_required"
        )
    return handler(args.aa_command, args)


def _run_profile_normalization(args: argparse.Namespace, normalizer: ProfileNormalizer | None) -> CliResult:
    if normalizer is None:
        return CliResult(
            exit_code=EXIT_CODES["validation_failed"], changed=False, error_reason="profile_normalizer_required"
        )
    return normalizer(args)


def _run_provider_sweep(args: argparse.Namespace, sweeper: ProviderSweeper | None) -> CliResult:
    if not args.provider:
        return CliResult(exit_code=EXIT_CODES["validation_failed"], changed=False, error_reason="provider_required")
    if sweeper is None:
        return CliResult(exit_code=EXIT_CODES["success"], changed=False)
    result = sweeper(args)
    return CliResult(
        exit_code=EXIT_CODES["success"],
        changed=bool(getattr(result, "changed", False)),
        output=format_provider_sweep_result(result, as_json=args.json),
    )


def _run_diagnostics(args: argparse.Namespace, diagnostics_reader: DiagnosticsReader | None) -> CliResult:
    if args.command == "explain-endpoint":
        identifier = args.endpoint
        kind = "endpoint"
    else:
        identifier = args.role
        kind = "role"
    if not identifier:
        return CliResult(exit_code=EXIT_CODES["validation_failed"], changed=False, error_reason=f"{kind}_required")
    if diagnostics_reader is None:
        return CliResult(exit_code=EXIT_CODES["success"], changed=False, output=None)
    return CliResult(exit_code=EXIT_CODES["success"], changed=False, output=diagnostics_reader(kind, identifier))


def _run_scheduler(args: argparse.Namespace, scheduler_runner: SchedulerRunner | None) -> CliResult:
    if scheduler_runner is None:
        return CliResult(exit_code=EXIT_CODES["success"], changed=False)
    while True:
        result = scheduler_runner(_utc_timestamp())
        if args.run_once:
            return result
        time.sleep(60)


def _utc_timestamp() -> str:
    return utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    parser.add_argument("--run-once", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
