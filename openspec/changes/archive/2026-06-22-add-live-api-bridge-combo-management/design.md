# Design: Live API bridge combo management

## Context

FMO's apply path needs the live OmniRoute combo set before mutation, then needs
to update existing `fmo-` combo membership and read back the result. The live
bridge already fronts OpenAI-compatible routes and selected FMO read routes, but
currently returns bridge-level `404` for `/api/combos*`.

OmniRoute owns management auth on the combo routes:

- `GET /api/combos` lists combos.
- `GET /api/combos/{id}` reads one combo.
- `PUT /api/combos/{id}` updates an existing combo.
- `DELETE /api/combos/{id}` exists upstream but FMO remains forbidden to delete.
- `POST /api/combos/test` remains forbidden for FMO.

## Goals

- Let FMO use the live bridge for combo management read/write.
- Preserve OmniRoute's `requireManagementAuth` behavior.
- Preserve FMO's existing safety rules: rebalance only existing `fmo-` combos,
  never create/delete, drift protection, smoke through OpenAI-compatible combo
  model, rollback on failure.
- Make live verification repeatable and documented.

## Non-Goals

- No public `/v1/combos` management projection.
- No enablement of `/api/combos/test`.
- No broadened provider/connection write surface.
- No code or fixture edits in proposal creation.

## Decision

The bridge shall explicitly allow only the management combo paths FMO needs for
apply:

```text
GET /api/combos
GET /api/combos/{id}
PUT /api/combos/{id}
```

The bridge forwards those requests with their management auth headers to
OmniRoute. The bridge shall not synthesize combo responses and shall not translate
auth failures into route-missing failures. If auth is absent or invalid,
OmniRoute returns its management-auth failure. If the route is allowed and
OmniRoute cannot serve it, the upstream response is surfaced.

## Pseudocode

```python
def bridge_allows(method: str, path: str) -> bool:
    if method == "GET" and path == "/api/combos":
        return True
    if method in {"GET", "PUT"} and re.fullmatch(r"/api/combos/[^/]+", path):
        return True
    return existing_bridge_policy_allows(method, path)


def read_current_combos(client):
    payload = client.get("/api/combos")
    return {combo["id"]: normalize_models(combo) for combo in payload["combos"]}


def apply_existing_combo(client, combo_id, desired_models, idempotency_key):
    current = read_current_combos(client)
    if combo_id not in current:
        return unmanaged_combo(combo_id)

    client.put(
        f"/api/combos/{combo_id}",
        {"models": desired_models},
        idempotency_key=idempotency_key,
    )
    read_back = client.get(f"/api/combos/{combo_id}")
    assert_membership_matches(read_back, desired_models)
```

## Live Verification

Before implementation, verify current failure:

```bash
curl -i -H "Authorization: Bearer $OMNIROUTE_MANAGEMENT_KEY" \
  http://127.0.0.1:20129/api/combos
```

Expected before this change: bridge-level `404`.

After implementation, verify:

- authorized `GET /api/combos` reaches OmniRoute and returns combo JSON;
- unauthenticated `GET /api/combos` reaches OmniRoute auth and returns auth
  failure, not bridge-level `404`;
- authorized `GET /api/combos/{id}` reaches OmniRoute for a real combo;
- authorized `PUT /api/combos/{id}` can update an existing test-managed combo
  only during approved live mutation verification;
- `POST /api/combos/test` remains unavailable to FMO.

## Risks

- Allowing too broad a bridge prefix would expose unrelated management routes.
  Mitigation: method/path allowlist, tests for denied helper/delete routes.
- FMO may currently use a method that differs from live OmniRoute's update
  route. Mitigation: align writer to `PUT /api/combos/{id}` during
  implementation and cover with executable specs.
- Live mutation verification can change operator combos. Mitigation: read-only
  verification by default; mutation only on an approved test-managed combo.
