# Vulture whitelist — intentionally-unreferenced names.
#
# Vulture cannot see that these are part of a public/stable signature or are
# accessed dynamically, so it reports them as dead. Listing them here keeps
# `vulture` (and the `[tool.vulture]` gate) at zero noise. Run with the file:
#
#     vulture src whitelist.py
#
# Remove an entry the moment the real reference is added — a stale whitelist
# hides regressions just as effectively as it hides false positives.

# Parameters kept for signature/interface stability (callers pass them by name):
thresholds          # aa_migration.detect_index_change — reserved for threshold-gated migration
model_endpoint_check  # config.validate_startup — optional probe injected by some callers
daily_refresh       # web_cookie endpoint builder — flag threaded through for parity with siblings
