# fix-apply-smoke-response-shape

## Why

The production apply smoke test reads a body-level `status_code` field from the
chat completion response:

```python
# src/fmo/composition_stages.py:_smoke_combo
return response.get("status_code") == 200 and bool(response.get("content", "ok"))
```

OmniRoute `/v1/chat/completions` is OpenAI-compatible: the success/failure
status is the HTTP status (already enforced by `OmniRouteClient._request`, which
raises `OmniRouteRequestError` on non-2xx), and the body is an OpenAI shape
(`choices[0].message.content`) with **no** top-level `status_code` field. The
current check only passes against the in-repo fake client
(`tests/test_composition.py::PipelineOpsClient`, which returns
`{"status_code": 200, "content": "ok"}`) — a hand-fabricated shape that violates
the project's "mock realistically" rule.

Against a real OmniRoute instance `response.get("status_code")` is always
`None`, so the smoke test always returns `False`, every `apply` rolls back, and
the pipeline can never commit a combo (`apply_failed_rolled_back`, exit 6). The
`bool(response.get("content", "ok"))` clause is also dead: the `"ok"` default
makes it unconditionally truthy.

## What Changes

- Reshape `_smoke_combo` to treat a non-raising POST as the HTTP-200 signal and
  derive success from the OpenAI-compatible body
  (`choices[0].message.content` present and non-empty), not a fabricated
  body-level `status_code`.
- Treat an `OmniRouteRequestError` (non-2xx HTTP) from the smoke POST as a smoke
  failure that triggers rollback, not an unhandled crash.
- Replace the fabricated `{"status_code", "content"}` smoke fixtures in the test
  suite with a recorded real OmniRoute `/v1/chat/completions` body shape
  (`../OmniRoute`), covering a valid completion, an empty/refusal completion, and
  a non-2xx HTTP error.

## Impact

- Modified spec: `combo-applier` (Production apply invokes the real smoke path).
- Affected code: `src/fmo/composition_stages.py` (`_smoke_combo`), test fakes in
  `tests/test_composition.py` / `tests/test_advisory.py`.
- Depends on: nothing new; OmniRoute already returns OpenAI-compatible bodies.
- Risk: this is the second prod-deploy blocker — without it apply never commits.
