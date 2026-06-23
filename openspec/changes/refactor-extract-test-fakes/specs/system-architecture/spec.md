## ADDED Requirements

### Requirement: Shared test fakes and per-domain composition tests

Shared test fakes SHALL live in a dedicated `tests` support module rather than
inline in a single test file (fake OmniRoute/ops clients, LLM runtimes, and
instructor clients), and the composition tests SHALL be split into per-domain
files that
mirror the stage cluster modules, with every `@pytest.mark.spec` binding moving
with its test. The test suite SHALL collect and run identically under both
`pytest` and `python -m pytest`. Reorganizing the tests SHALL NOT drop any
scenario binding; `test_spec_coverage.py` is the oracle that coverage is
preserved.

#### Scenario: Test fakes live in a shared test-support module
- **WHEN** a test needs a fake ops client, LLM runtime, or instructor client
- **THEN** it imports the fake from the shared `tests` support module
- **AND** no composition test file redefines those fakes inline

#### Scenario: Composition tests mirror the stage packages
- **WHEN** the composition tests are inspected
- **THEN** they are split into per-domain files mirroring the stage cluster
  modules, with each `@pytest.mark.spec` marker carried alongside its test
- **AND** `test_spec_coverage.py` reports every previously bound scenario still
  bound

#### Scenario: Test suite runs from both pytest entry points
- **WHEN** the suite is collected via either `pytest` or `python -m pytest`
- **THEN** the `tests` package resolves without depending on the current working
  directory being on `sys.path`
- **AND** both entry points collect and pass the same tests
