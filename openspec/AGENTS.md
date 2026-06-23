# OpenSpec Instructions

Spec-driven dev rules for AI coding agents.

## TL;DR

- Search: `openspec spec list --long`, `openspec list`; use `rg` only for full-text.
- Scope: new capability vs existing capability change.
- ID: unique kebab-case verb-led `change-id`: `add-`, `update-`, `remove-`, `refactor-`.
- Files: `proposal.md`, `tasks.md`, optional `design.md`, delta specs per affected capability.
- Deltas: `## ADDED|MODIFIED|REMOVED|RENAMED Requirements`.
- Every requirement needs `#### Scenario:`.
- Validate: `npx --yes @fission-ai/openspec@latest validate <change-id> --strict`; fix before sharing.
- Gate: no impl before proposal approval.

## Workflow

### 1. Create Change

Create proposal for new feature/functionality, breaking API/schema, architecture/pattern change, behavior-changing perf optimization, security pattern update.

Trigger examples: "create change proposal", "plan change", "create proposal", "spec proposal", "create spec". Loose match: `proposal|change|spec` plus `create|plan|make|start|help`.

Skip proposal for bug fix restoring intended behavior, typo/format/comment, non-breaking dependency update, config change, tests for existing behavior.

Steps:
1. Review `openspec/project.md`, `openspec list`, `openspec list --specs`.
2. Choose unique verb-led `change-id`.
3. Create `openspec/changes/<id>/proposal.md`, `tasks.md`, optional `design.md`, specs deltas.
4. Draft deltas with valid operation headers.
5. Run `openspec validate <id> --strict`; fix all.

### 2. Implement Change

1. Read `proposal.md`.
2. Read `design.md` if present.
3. Read `tasks.md`.
4. Implement tasks in order.
5. Confirm every `tasks.md` item done before status update.
6. Review `AICODE-NOTE:`, `AICODE-TODO:`, `AICODE-QUESTION:`.
7. Use human-in-the-loop for questions.
8. Implement related in-scope `AICODE-TODO:` where possible.
9. Set complete tasks to `- [x]`.

Gate still applies: no impl before reviewed/approved proposal.

### 3. Archive Change

After deployment, separate PR:
- Move `changes/[name]/` -> `changes/archive/YYYY-MM-DD-[name]/`.
- Update `specs/` if capability changed.
- Tooling-only: `openspec archive <change-id> --skip-specs --yes`.
- Always pass explicit change ID.
- Run `openspec validate --strict`.

## Before Any Task

Checklist:
- [ ] Read relevant `specs/[capability]/spec.md`.
- [ ] Check pending `changes/` conflicts.
- [ ] Read `openspec/project.md`.
- [ ] Run `openspec list`.
- [ ] Run `openspec list --specs`.

Before specs: check existing capability, prefer modifying over duplicate, use `openspec show <spec>`, ask 1-2 clarifying questions if ambiguous.

## Search / CLI

```bash
npx --yes @fission-ai/openspec@latest spec list --long
npx --yes @fission-ai/openspec@latest list
npx --yes @fission-ai/openspec@latest change list --json
npx --yes @fission-ai/openspec@latest show <spec-id> --type spec
npx --yes @fission-ai/openspec@latest show <change-id> --json --deltas-only
rg -n "Requirement:|Scenario:" openspec/specs

# Essential
npx --yes @fission-ai/openspec@latest list
npx --yes @fission-ai/openspec@latest list --specs
npx --yes @fission-ai/openspec@latest show [item]
npx --yes @fission-ai/openspec@latest validate [item]
npx --yes @fission-ai/openspec@latest archive <change-id> [--yes|-y]
npx --yes @fission-ai/openspec@latest validate <change-id> --strict
npx --yes @fission-ai/openspec@latest archive <change-id> --yes

# Project / interactive / debug
npx --yes @fission-ai/openspec@latest init [path]
npx --yes @fission-ai/openspec@latest update [path]
npx --yes @fission-ai/openspec@latest show
npx --yes @fission-ai/openspec@latest validate
npx --yes @fission-ai/openspec@latest show [change] --json --deltas-only
npx --yes @fission-ai/openspec@latest validate [change] --strict
```

Flags: `--json` machine output; `--type change|spec` disambiguate; `--strict` full validation; `--no-interactive` no prompts; `--skip-specs` archive without spec updates; `--yes`/`-y` no archive confirm.

## Structure

```text
openspec/
├── project.md
├── specs/
│   └── [capability]/
│       ├── spec.md
│       └── design.md
├── changes/
│   ├── [change-name]/
│   │   ├── proposal.md
│   │   ├── tasks.md
│   │   ├── design.md
│   │   └── specs/[capability]/spec.md
│   └── archive/
```

## Proposal Authoring

Decision:

```text
New request?
├─ Bug fix restoring spec behavior? -> Fix directly
├─ Typo/format/comment? -> Fix directly
├─ New feature/capability? -> Create proposal
├─ Breaking change? -> Create proposal
├─ Architecture change? -> Create proposal
└─ Unclear? -> Create proposal
```

Create `changes/[change-id]/` with unique verb-led kebab-case ID.

`proposal.md`:

```markdown
# Change: [Brief description]

## Why
[Problem/opportunity in 1-2 sentences]

## What Changes
- [Change]
- [Mark breaking changes with **BREAKING**]

## Impact
- Affected specs: [capabilities]
- Affected code: [files/systems]
```

`tasks.md`:

```markdown
## 1. Implementation
- [ ] 1.1 Create database schema
- [ ] 1.2 Implement API endpoint
- [ ] 1.3 Add frontend component
- [ ] 1.4 Write tests
```

Delta file: `changes/[change-id]/specs/[capability]/spec.md`

```markdown
## ADDED Requirements
### Requirement: New Feature
The system SHALL provide...

#### Scenario: Success case
- **WHEN** user performs action
- **THEN** expected result

## MODIFIED Requirements
### Requirement: Existing Feature
[Full updated requirement]

## REMOVED Requirements
### Requirement: Old Feature
**Reason**: [Why removing]
**Migration**: [How to handle]
```

Multiple capabilities -> one delta file per capability.

Create `design.md` only for cross-cutting/new architecture, new dependency/big data model, security/perf/migration complexity, or ambiguity needing decisions before code.

```markdown
## Context
[Background, constraints, stakeholders]

## Goals / Non-Goals
- Goals: [...]
- Non-Goals: [...]

## Decisions
- Decision: [What and why]
- Alternatives considered: [Options + rationale]

## Risks / Trade-offs
- [Risk] -> Mitigation

## Migration Plan
[Steps, rollback]

## Open Questions
- [...]
```

## Spec Format

Correct:

```markdown
#### Scenario: User login success
- **WHEN** valid credentials provided
- **THEN** return JWT token
```

Wrong:

```markdown
- **Scenario: User login**
**Scenario**: User login
### Scenario: User login
```

Rules: every requirement MUST have at least one scenario; use SHALL/MUST for normative reqs; avoid should/may unless non-normative.

## Delta Operations

- `## ADDED Requirements`: new standalone capability/sub-capability.
- `## MODIFIED Requirements`: changed behavior/scope/acceptance criteria. Paste full updated requirement, header plus all scenarios. Partial deltas drop previous details during archive.
- `## REMOVED Requirements`: deprecated feature.
- `## RENAMED Requirements`: name-only change. If behavior changes too, use RENAMED plus MODIFIED referencing new name.

Headers match with `trim(header)`; whitespace ignored.

MODIFIED process:
1. Locate requirement in `openspec/specs/<capability>/spec.md`.
2. Copy full block from `### Requirement: ...` through scenarios.
3. Paste under `## MODIFIED Requirements`.
4. Edit behavior.
5. Keep exact header match and at least one `#### Scenario:`.

RENAMED:

```markdown
## RENAMED Requirements
- FROM: `### Requirement: Login`
- TO: `### Requirement: User Authentication`
```

## Troubleshooting

- `"Change must have at least one delta"` -> ensure `changes/[name]/specs/` has `.md` files and operation headers.
- `"Requirement must have at least one scenario"` -> use exact `#### Scenario:`; no bullet/bold scenario headers.
- Silent scenario parse failure -> exact `#### Scenario: Name`; debug with `openspec show [change] --json --deltas-only`.

```bash
openspec validate [change] --strict
openspec show [change] --json | jq '.deltas'
openspec show [spec] --json -r 1
```

## Happy Path

```bash
openspec spec list --long
openspec list
# rg -n "Requirement:|Scenario:" openspec/specs
# rg -n "^#|Requirement:" openspec/changes

CHANGE=add-two-factor-auth
mkdir -p openspec/changes/$CHANGE/{specs/auth}
printf "## Why\n...\n\n## What Changes\n- ...\n\n## Impact\n- ...\n" > openspec/changes/$CHANGE/proposal.md
printf "## 1. Implementation\n- [ ] 1.1 ...\n" > openspec/changes/$CHANGE/tasks.md

cat > openspec/changes/$CHANGE/specs/auth/spec.md << 'EOF'
## ADDED Requirements
### Requirement: Two-Factor Authentication
Users MUST provide a second factor during login.

#### Scenario: OTP required
- **WHEN** valid credentials are provided
- **THEN** an OTP challenge is required
EOF

openspec validate $CHANGE --strict
```

Multi-capability shape:

```text
openspec/changes/add-2fa-notify/
├── proposal.md
├── tasks.md
└── specs/
    ├── auth/spec.md
    └── notifications/spec.md
```

## Best Practices

- Before scanning, grep existing `AICODE-...`.
- Use/update `AICODE-NOTE:`, `AICODE-TODO:`, `AICODE-QUESTION:`.
- Add anchors for complex, important, or bug-prone code.
- Default to <100 lines new code, single-file impl until insufficient, boring proven patterns.
- Add complexity only with perf data, concrete scale reqs (>1000 users or >100MB data), or multiple proven abstraction use cases.
- Use refs: `file.ts:42`, `specs/auth/spec.md`, related changes/PRs.
- Capability names: verb-noun (`user-auth`, `payment-capture`), single purpose, 10-min understandable, split if needs "AND".
- Change IDs: short kebab-case, descriptive, `add-`/`update-`/`remove-`/`refactor-`, unique; append `-2`, `-3` if taken.

## Tools / Recovery

| Task | Tool | Why |
|------|------|-----|
| Find files by pattern | Glob | Fast pattern matching |
| Search code content | Grep | Optimized regex search |
| Read specific files | Read | Direct file access |
| Explore unknown scope | Task | Multi-step investigation |

Conflicts: run `openspec list`, check overlapping specs, coordinate owners, consider combining proposals.

Validation failures: run `--strict`, inspect JSON, verify spec format, verify exact scenario headers.

Missing context: read `project.md`, check related specs, review recent archives, ask clarification.

## Quick Ref

- `changes/`: proposed, not built.
- `specs/`: built and deployed.
- `archive/`: completed.
- `proposal.md`: why/what.
- `tasks.md`: impl checklist.
- `design.md`: technical decisions.
- `spec.md`: requirements/behavior.

```bash
openspec list
openspec show [item]
openspec validate --strict
openspec archive <change-id> [--yes|-y]
```

Specs = truth. Changes = proposals. Keep sync.
