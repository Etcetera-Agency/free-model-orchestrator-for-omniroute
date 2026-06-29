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
from fmo.idempotency import utcnow

COMMANDS = [
    "sync-hermes-inventory",
    "reconcile-roles",
    "forecast-demand",
    "full",
    "serve",
    "explain-role",
    "normalize-profiles",
]

EXIT_CODES = {
    "success": 0,
    "partial_stale": 2,
    "validation_failed": 3,
    "external_dependency_failed": 4,
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
ProfileNormalizer = Callable[[argparse.Namespace], CliResult]


PIPELINE_COMMANDS = {
    "sync-hermes-inventory",
    "reconcile-roles",
    "forecast-demand",
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="free-model-orchestrator")
    _add_common_flags(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        _add_common_flags(subparsers.add_parser(command))
    return parser.parse_args(argv)


def run_cli(
    argv: list[str],
    *,
    preconditions_ok: bool,
    pipeline_runner: PipelineRunner | None = None,
    diagnostics_reader: DiagnosticsReader | None = None,
    scheduler_runner: SchedulerRunner | None = None,
    profile_normalizer: ProfileNormalizer | None = None,
) -> CliResult:
    del preconditions_ok
    args = parse_args(argv)
    if args.command == "normalize-profiles":
        return _run_profile_normalization(args, profile_normalizer)
    if args.command == "serve":
        return _run_scheduler(args, scheduler_runner)
    if args.command == "explain-role":
        return _run_diagnostics(args, diagnostics_reader)
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
        profile_normalizer=cast(ProfileNormalizer, runtime.normalize_profiles),
    )
    if result.output:
        print(result.output)
    return result.exit_code


def _run_profile_normalization(args: argparse.Namespace, normalizer: ProfileNormalizer | None) -> CliResult:
    if normalizer is None:
        return CliResult(
            exit_code=EXIT_CODES["validation_failed"], changed=False, error_reason="profile_normalizer_required"
        )
    return normalizer(args)


def _run_diagnostics(args: argparse.Namespace, diagnostics_reader: DiagnosticsReader | None) -> CliResult:
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
