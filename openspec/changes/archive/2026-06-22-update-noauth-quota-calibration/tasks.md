## 1. Specification

- [x] 1.1 Document no-auth provider aliasing in quota research.
- [x] 1.2 Document unknown no-auth calibration through combo-first placement and OmniRoute token-usage observation.
- [x] 1.3 Validate the OpenSpec change strictly.

## 2. Future implementation

- [x] 2.1 Add an explicit no-auth alias map seeded with `opencode -> opencode-zen`.
- [x] 2.2 Mark no-auth providers with unknown quota as calibration-required instead of usable.
- [x] 2.3 Add operator tooling or runbook steps to place a calibration provider first in a controlled combo.
- [x] 2.4 Persist observed OmniRoute token usage as a quota source before activating capacity.
