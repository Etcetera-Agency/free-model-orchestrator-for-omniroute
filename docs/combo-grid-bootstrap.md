# Combo grid bootstrap — combos to create on the server

<!-- AICODE-NOTE: This runbook captures production port/key/backup pitfalls from
the 2026-06-23 combo replacement; keep it executable after OmniRoute bridge or
management-auth changes. -->

Input list for a **separate task**: create the default combo grid on the live
OmniRoute. Design rationale lives in the `add-intelligence-inspector` openspec
change (`proposal.md` / `design.md`) and the deploy runbook
(`ORACLE_FRESH_SERVER_DEPLOY.md` §7a). This file is just the concrete list.

## Rules (read before creating)

- **One-time bootstrap, minimal.** Each combo is created with a **single seed
  model** that sets the cell's anchor. Do NOT pre-fill member lists — the
  agent-driven rebalance grows each combo later (`quality_band_for_demand`).
- **Seeds below are CANDIDATES from fixture data and must be regenerated with the
  FMO matcher** (`src/fmo/matcher.py` + `aa_index_runtime`) against live AA +
  registered models before creation. They came from fuzzy name matching, which
  mislabels models; do not paste them into a live combo unverified.
- **Replacement bootstrap.** Create all grid combos first, verify they exist, then
  delete the old non-grid `fmo-*` combos. Do not delete old combos before the full
  grid exists. Back up `GET /api/combos` to `bak-wf/` first.
- **Create payload shape** (per `/api/combos`): `{ name, models: [{ kind:"model",
  model:"<provider/id>", providerId, weight:0 }], strategy:"priority" }`.
- **Management writes use dashboard port.** On production, `20129` is the API
  bridge; it may allow `GET /api/combos` but blocks `POST /api/combos` with
  `API port only serves OpenAI-compatible and approved read-only management
  routes.` Use `http://127.0.0.1:20128/api/combos` from inside the `omniroute`
  container for create/delete writes.
- **Use `docker exec -i` for heredocs.** Without `-i`, Node receives no script,
  temp key creation silently yields an empty shell variable, and later requests
  return `401`.
- **Backups are host files.** Do not write `/opt/apps/omniroute/bak-wf` from
  inside the container. Stream the container API response to host `sudo tee`.
- Hard filters that define each cell (applied by the matcher when picking the
  seed and later members): `required_capabilities` (`issubset`) and context window
  (`effective_context_window ≥ minimum`). Context class here is the **default**
  (≥128k); large-context variants are minted on demand, not at bootstrap.

## A. Axis × tier grid (9 combos)

Tiers = per-axis tertiles of the registered text pool; anchor = median of the band.
Reference cuts (2026-06-22 fixture, regenerate live): int 10.0/29.4, cod 15.5/37.4,
agt 18.8/53.2.

| combo name          | axis               | tier   | anchor≈ | seed candidate (verify)                       |
|---------------------|--------------------|--------|---------|-----------------------------------------------|
| `fmo-grid-int-low`  | intelligence_index | low    | 7.3     | `nvidia/mistralai/mistral-large-2-instruct`   |
| `fmo-grid-int-med`  | intelligence_index | medium | 20.1    | `antigravity/gemini-2.5-flash`                |
| `fmo-grid-int-high` | intelligence_index | high   | 38.1    | `nvidia/minimaxai/minimax-m2.7`               |
| `fmo-grid-cod-low`  | coding_index       | low    | 10.0    | `mistral/ministral-8b-2512`                   |
| `fmo-grid-cod-med`  | coding_index       | medium | 25.2    | `ollamacloud/qwen3-coder:480b`                |
| `fmo-grid-cod-high` | coding_index       | high   | 42.9    | `oc/qwen3.6-plus-free`                        |
| `fmo-grid-agt-low`  | agentic_index      | low    | 8.5     | `nvidia/nvidia/nemotron-3-nano-30b-a3b`       |
| `fmo-grid-agt-med`  | agentic_index      | medium | 30.1    | `antigravity/gpt-oss-120b-medium`             |
| `fmo-grid-agt-high` | agentic_index      | high   | 61.7    | `oc/qwen3.6-plus-free`                        |

## B. Auxiliary family (4 combos)

Cheapest model satisfying the required capability (no Inspector call). The existing
aux combos point at the matching family member.

| combo name           | required capability | seed candidate (verify)              | feeds (existing aux combos)                                   |
|----------------------|---------------------|--------------------------------------|--------------------------------------------------------------|
| `fmo-grid-aux-text`  | none (plain text)   | `nvidia/google/gemma-3n-e2b-it`      | `fmo-title-generation`, `fmo-compression`, `fmo-curator`, `fmo-profile-describer` |
| `fmo-grid-aux-tools` | `tool_calling`      | `nvidia/google/gemma-3n-e2b-it`      | `fmo-mcp`, `fmo-skills`, `fmo-triage-specifier`, `fmo-kanban-decomposer` |
| `fmo-grid-aux-struct`| structured output   | `nvidia/google/gemma-3n-e2b-it`      | `fmo-approval`                                                |
| `fmo-grid-aux-vision`| `vision`            | `antigravity/gemini-2.5-flash-lite`  | `fmo-vision`                                                  |

Note: `aux-text`/`aux-tools`/`aux-struct` seed to the same cheapest model only
because it happens to carry `tool_calling`; their capability filters diverge the
combos during rebalance.

## C. Legacy role combos

Delete old role and auxiliary combos only after all grid combos have been created
and verified:

```text
fmo-chat-combo
fmo-research-combo
fmo-coding-combo
fmo-title-generation
fmo-vision
fmo-compression
fmo-approval
fmo-skills
fmo-mcp
fmo-triage-specifier
fmo-kanban-decomposer
fmo-profile-describer
fmo-curator
```

## Capacity warnings (thin corners — expect band `degraded`)

- high-intelligence registered endpoints ≈38 (≈13 models, quota-shared per provider)
- 1M+ context ≈58 endpoints; `aux-vision` draws from `vision` ≈52 endpoints

## Bootstrap step (server, back up first)

```bash
ssh -o BatchMode=yes etc2nd-shlink 'bash -s' <<'REMOTE'
set -eu

pair=$(sudo docker exec -i omniroute node - <<'KEYNODE'
const crypto = require('crypto');
const Database = require('better-sqlite3');
const db = new Database('/app/data/storage.sqlite');
const id = crypto.randomUUID();
const machine =
  (db.prepare('select machine_id from api_keys where machine_id is not null limit 1').get() || {})
    .machine_id || 'combo-bootstrap';
const key = 'omr_boot_' + crypto.randomBytes(32).toString('base64url');
const hash = crypto.createHash('sha256').update(key).digest('hex');
const now = new Date().toISOString();
db.prepare(
  'insert into api_keys (id,name,key,machine_id,allowed_models,no_log,created_at,key_prefix,key_hash,scopes,is_active) values (?,?,?,?,?,?,?,?,?,?,1)'
).run(
  id,
  'fmo-combo-bootstrap-temp',
  key,
  machine,
  '[]',
  1,
  now,
  key.slice(0, 12),
  hash,
  JSON.stringify(['manage'])
);
db.close();
console.log(id + ' ' + key);
KEYNODE
)

temp_id=${pair%% *}
key=${pair#* }
cleanup() {
  sudo docker exec omniroute node -e \
    "const Database=require('better-sqlite3');const db=new Database('/app/data/storage.sqlite');db.prepare('delete from api_keys where id=?').run(process.argv[1]);db.close();" \
    "$temp_id" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sudo install -d -m 0750 /opt/apps/omniroute/bak-wf
backup="/opt/apps/omniroute/bak-wf/combos-$(date -u +%Y%m%d-%H%M%S).json"
sudo docker exec -i -e KEY="$key" omniroute node - <<'BACKUPNODE' | sudo tee "$backup" >/dev/null
(async () => {
  const res = await fetch('http://127.0.0.1:20128/api/combos', {
    headers: { Authorization: 'Bearer ' + process.env.KEY },
  });
  if (!res.ok) throw new Error('GET /api/combos ' + res.status);
  console.log(await res.text());
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
BACKUPNODE

payload=$(cat <<'JSON'
[
  ["fmo-grid-int-low","nvidia/mistralai/mistral-large-2-instruct"],
  ["fmo-grid-int-med","antigravity/gemini-2.5-flash"],
  ["fmo-grid-int-high","nvidia/minimaxai/minimax-m2.7"],
  ["fmo-grid-cod-low","mistral/ministral-8b-2512"],
  ["fmo-grid-cod-med","ollamacloud/qwen3-coder:480b"],
  ["fmo-grid-cod-high","oc/qwen3.6-plus-free"],
  ["fmo-grid-agt-low","nvidia/nvidia/nemotron-3-nano-30b-a3b"],
  ["fmo-grid-agt-med","antigravity/gpt-oss-120b-medium"],
  ["fmo-grid-agt-high","oc/qwen3.6-plus-free"],
  ["fmo-grid-aux-text","nvidia/google/gemma-3n-e2b-it"],
  ["fmo-grid-aux-tools","nvidia/google/gemma-3n-e2b-it"],
  ["fmo-grid-aux-struct","nvidia/google/gemma-3n-e2b-it"],
  ["fmo-grid-aux-vision","antigravity/gemini-2.5-flash-lite"]
]
JSON
)

sudo docker exec -i \
  -e KEY="$key" \
  -e PAYLOAD="$payload" \
  -e BACKUP="$backup" \
  omniroute node - <<'APINODE'
const key = process.env.KEY;
const desired = JSON.parse(process.env.PAYLOAD);

async function req(base, path, opts = {}) {
  const res = await fetch(base + path, {
    ...opts,
    headers: {
      Authorization: 'Bearer ' + key,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }
  return { status: res.status, body, text };
}

const mgmt = 'http://127.0.0.1:20128';
const api = 'http://127.0.0.1:20129';
const combosRes = await req(mgmt, '/api/combos');
if (combosRes.status !== 200) throw new Error('GET /api/combos status ' + combosRes.status);
const modelsRes = await req(api, '/v1/models');
if (modelsRes.status !== 200) throw new Error('GET /v1/models status ' + modelsRes.status);

const byId = new Map((modelsRes.body.data || []).map((model) => [model.id, model]));
const desiredNames = new Set(desired.map(([name]) => name));
const beforeCombos = combosRes.body.combos || [];
const existing = new Set(beforeCombos.map((combo) => combo.name));
const oldCombos = beforeCombos.filter((combo) => !desiredNames.has(combo.name));
const created = [];
const skipped = [];

for (const [name, modelId] of desired) {
  if (existing.has(name)) {
    skipped.push({ name, reason: 'exists' });
    continue;
  }
  const model = byId.get(modelId);
  if (!model) throw new Error('seed missing ' + modelId);
  const providerId = model.owned_by || model.provider || modelId.split('/')[0];
  const payload = {
    name,
    models: [{ kind: 'model', model: modelId, providerId, weight: 0 }],
    strategy: 'priority',
  };
  const res = await req(mgmt, '/api/combos', { method: 'POST', body: JSON.stringify(payload) });
  if (res.status !== 201) {
    throw new Error('POST ' + name + ' status ' + res.status + ' body ' + res.text.slice(0, 500));
  }
  created.push({ name, model: modelId, providerId });
}

const verifyCreated = await req(mgmt, '/api/combos');
const verifyNames = new Set((verifyCreated.body.combos || []).map((combo) => combo.name));
const missingAfterCreate = desired.map(([name]) => name).filter((name) => !verifyNames.has(name));
if (missingAfterCreate.length) {
  throw new Error('missing after create: ' + missingAfterCreate.join(', '));
}

const deleted = [];
for (const combo of oldCombos) {
  const res = await req(mgmt, '/api/combos/' + encodeURIComponent(combo.id), { method: 'DELETE' });
  if (res.status !== 200) {
    throw new Error('DELETE ' + combo.name + ' status ' + res.status + ' body ' + res.text.slice(0, 500));
  }
  deleted.push({ name: combo.name, id: combo.id });
}

const after = await req(mgmt, '/api/combos');
const finalCombos = after.body.combos || [];
const finalNames = finalCombos.map((combo) => combo.name).sort();
const missing = desired.map(([name]) => name).filter((name) => !finalNames.includes(name));
const leftovers = finalNames.filter((name) => !desiredNames.has(name));
console.log(
  JSON.stringify(
    {
      backup: process.env.BACKUP,
      created,
      skipped,
      deleted,
      missing,
      leftovers,
      totalCombosBefore: beforeCombos.length,
      totalCombosFinal: finalCombos.length,
    },
    null,
    2
  )
);
APINODE
REMOTE
```

## Verification and cleanup

```bash
ssh -o BatchMode=yes etc2nd-shlink "sudo docker exec omniroute node -e '
const Database=require(\"better-sqlite3\");
const db=new Database(\"/app/data/storage.sqlite\",{readonly:true});
console.log((db.prepare(\"select count(*) as n from api_keys where name=?\").get(\"fmo-combo-bootstrap-temp\")||{}).n);
db.close();
'"
```

Expected temp-key count: `0`.

```bash
ssh -o BatchMode=yes etc2nd-shlink "sudo docker exec omniroute node -e '
const Database=require(\"better-sqlite3\");
const db=new Database(\"/app/data/storage.sqlite\",{readonly:true});
console.log(JSON.stringify(db.prepare(\"select name from combos order by name\").all().map((row)=>row.name),null,2));
db.close();
'"
```

Expected final list: exactly the 13 `fmo-grid-*` combos, no old
`fmo-chat-combo` / auxiliary combos.

Delete only zero-byte failed backup stubs. Keep the real pre-mutation backup:

```bash
ssh -o BatchMode=yes etc2nd-shlink \
  "sudo find /opt/apps/omniroute/bak-wf -maxdepth 1 -type f -name 'combos-*.json' -size 0 -print -delete"
```

## Pitfalls from 2026-06-23 run

- `docker exec omniroute node - <<'NODE'` without `-i` does not feed the heredoc
  into Node. Symptom: temp key variable is empty and API reads return `401`.
- Writing backup path from inside the container fails with `EACCES: permission
  denied, mkdir '/opt/apps/omniroute/bak-wf'`. Create/write backup on host with
  `sudo install` and `sudo tee`.
- `POST /api/combos` on port `20129` fails with bridge `404`. Use port `20128`
  for management writes from inside `omniroute`.
- Failed attempts may leave zero-byte backup files; remove those after confirming
  a non-empty backup exists.
