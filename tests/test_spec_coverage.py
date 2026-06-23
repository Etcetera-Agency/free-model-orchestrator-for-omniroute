"""Executable-spec gate.

A scenario is "known" if it is shipped (``openspec/specs/**/spec.md``) or
proposed in an active, non-archived change
(``openspec/changes/<id>/specs/**/spec.md``) — so TDD tests written before a
change is archived may bind to it. Each ``#### Scenario:`` is bound to a real
pytest test by marking that test with
``@pytest.mark.spec("<capability>::<Scenario name>")``. This module statically
cross-references scenarios against markers (independent of which test subset is
selected) and fails the build on drift in either direction:

- a scenario with no test and not on the pending allowlist;
- a marker pointing at a scenario that is neither shipped nor proposed;
- a pending entry that is actually covered (the allowlist must shrink);
- a pending entry referencing a scenario that no longer exists.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = ROOT / "openspec" / "specs"
CHANGES_DIR = ROOT / "openspec" / "changes"
TESTS_DIR = Path(__file__).resolve().parent
PENDING_FILE = TESTS_DIR / "spec_coverage_pending.txt"

_SCENARIO_RE = re.compile(r"^#### Scenario:\s*(.+?)\s*$", re.MULTILINE)
_MARK_RE = re.compile(r"""mark\.spec\(\s*["']([^"']+)["']""")


def _scenarios_in(spec: Path) -> set[str]:
    capability = spec.parent.name
    return {f"{capability}::{name}" for name in _SCENARIO_RE.findall(spec.read_text(encoding="utf-8"))}


def scenarios_in_specs() -> set[str]:
    """Shipped living-spec scenarios plus scenarios proposed in active changes."""
    ids: set[str] = set()
    for spec in SPECS_DIR.rglob("spec.md"):
        ids |= _scenarios_in(spec)
    for spec in CHANGES_DIR.glob("*/specs/*/spec.md"):
        if "archive" in spec.parts:
            continue
        ids |= _scenarios_in(spec)
    return ids


def scenarios_marked_in_tests() -> set[str]:
    ids: set[str] = set()
    for path in TESTS_DIR.rglob("test_*.py"):
        if path.name == "test_spec_coverage.py":
            continue
        for scenario_id in _MARK_RE.findall(path.read_text(encoding="utf-8")):
            ids.add(scenario_id)
    return ids


def pending_ids() -> set[str]:
    if not PENDING_FILE.exists():
        return set()
    return {
        line.strip()
        for line in PENDING_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_no_marker_points_at_unknown_scenario():
    unknown = scenarios_marked_in_tests() - scenarios_in_specs()
    assert not unknown, f"@pytest.mark.spec points at scenarios absent from specs: {sorted(unknown)}"


def test_pending_allowlist_references_real_scenarios():
    stale = pending_ids() - scenarios_in_specs()
    assert not stale, f"pending allowlist references scenarios absent from specs: {sorted(stale)}"


def test_pending_entries_are_not_already_covered():
    both = pending_ids() & scenarios_marked_in_tests()
    assert not both, f"scenarios are both pending and covered — drop them from pending: {sorted(both)}"


def test_every_scenario_is_covered_or_pending():
    uncovered = scenarios_in_specs() - scenarios_marked_in_tests() - pending_ids()
    assert not uncovered, f"scenarios with no test and not on the pending allowlist: {sorted(uncovered)}"
