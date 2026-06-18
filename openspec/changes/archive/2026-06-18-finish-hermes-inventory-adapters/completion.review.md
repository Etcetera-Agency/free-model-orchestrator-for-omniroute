# Completion Review: finish-hermes-inventory-adapters

## Code Simplifier

- Removed an unused fixture import/test argument, replaced dynamic YAML import
  with a normal import, and wrapped the command-adapter fixture command.

## Verification

- `tests/test_hermes_inventory_real_shapes.py` and
  `tests/test_role_lifecycle.py` -> 15 passed.
- `.venv/bin/python -m pytest -q` -> 199 passed, 7 skipped.
- `openspec validate finish-hermes-inventory-adapters --strict` -> valid.
