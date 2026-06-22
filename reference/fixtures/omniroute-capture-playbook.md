# OmniRoute fixture capture playbook

Purpose: refresh real OmniRoute response fixtures in
`reference/fixtures/external-responses/` from the live `etc2nd-shlink`
deployment without persisting management credentials in repo artifacts.

## Preconditions

- Work from repo root:

```sh
cd /Users/theDay/Hermes/free-model-orchestrator-for-omniroute
```

- Server SSH alias works:

```sh
ssh -o BatchMode=yes etc2nd-shlink true
```

- OmniRoute API bridge is reachable inside the server/container at:

```text
http://127.0.0.1:20129
```

- Do not print values from `/opt/apps/omniroute/.env` or any API key file.
  The capture flow below creates a temporary manage-scope key inside SQLite,
  uses it only inside the remote container, deletes it in `finally`, and only
  returns sanitized HTTP responses.

## Capture live OmniRoute fixtures

This command refreshes live OmniRoute fixtures only. It does not refresh
models.dev or Artificial Analysis fixtures.

```sh
/Users/theDay/.nvm/versions/node/v24.1.0/bin/node <<'NODE'
const { execFileSync } = await import('node:child_process');
const fs = await import('node:fs/promises');
const path = await import('node:path');

const outDir = '/Users/theDay/Hermes/free-model-orchestrator-for-omniroute/reference/fixtures/external-responses';

function redactString(value) {
  return value
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[EMAIL]')
    .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '[UUID]')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, 'Bearer [REDACTED]')
    .replace(/(cookie=)[^\s;]+/gi, '$1[REDACTED]');
}

function sanitize(value, key = '') {
  if (Array.isArray(value)) return value.map((item) => sanitize(item));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, sanitize(v, k)]));
  }
  if (typeof value === 'string') {
    if (/api.?key|token|secret|cookie|password|authorization|credential|refresh|access/i.test(key)) {
      return value ? '[REDACTED]' : value;
    }
    return redactString(value);
  }
  return value;
}

function parseBody(text) {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function writeFixture(record, capturedAt) {
  const safe = sanitize({
    captured_at: capturedAt,
    source: 'omniroute-shlink-20129',
    name: record.name,
    method: record.method,
    path: record.path,
    status: record.status,
    headers: sanitize(record.headers),
    body: sanitize(parseBody(record.body)),
  });
  await fs.writeFile(path.join(outDir, `${record.name}.json`), JSON.stringify(safe, null, 2) + '\n');
}

const remoteScript = `const crypto=require('crypto');const Database=require('better-sqlite3');(async()=>{const db=new Database('/app/data/storage.sqlite');const tempId=crypto.randomUUID();try{const machine=(db.prepare('select machine_id from api_keys where machine_id is not null limit 1').get()||{}).machine_id||'fixtures';const key='omr_fixture_'+crypto.randomBytes(32).toString('base64url');const hash=crypto.createHash('sha256').update(key).digest('hex');const now=new Date().toISOString();db.prepare('insert into api_keys (id,name,key,machine_id,allowed_models,no_log,created_at,key_prefix,key_hash,scopes,is_active) values (?,?,?,?,?,?,?,?,?,?,1)').run(tempId,'fmo-fixture-temp',key,machine,'[]',1,now,key.slice(0,12),hash,JSON.stringify(['manage']));const requests=[['omniroute_v1_models','GET','/v1/models'],['omniroute_v1_search_providers','GET','/v1/search'],['omniroute_api_monitoring_health','GET','/api/monitoring/health'],['omniroute_api_combos','GET','/api/combos'],['omniroute_api_providers','GET','/api/providers'],['omniroute_api_free_models','GET','/api/free-models'],['omniroute_api_free_provider_rankings','GET','/api/free-provider-rankings'],['omniroute_api_free_tier_summary','GET','/api/free-tier/summary'],['omniroute_api_rate_limits','GET','/api/rate-limits'],['omniroute_api_usage_analytics','GET','/api/usage/analytics'],['omniroute_api_usage_quota','GET','/api/usage/quota'],['omniroute_api_v1_provider_models_openai','GET','/api/v1/providers/openai/models']];const out=[];for(const [name,method,urlPath] of requests){const res=await fetch('http://127.0.0.1:20129'+urlPath,{method,headers:{Authorization:'Bearer '+key}});const body=await res.text();out.push({name,method,path:urlPath,status:res.status,headers:Object.fromEntries(res.headers.entries()),body});}console.log(JSON.stringify(out));}finally{db.prepare('delete from api_keys where id=?').run(tempId);db.close();}})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});`;
const encoded = Buffer.from(remoteScript).toString('base64');
const stdout = execFileSync(
  'ssh',
  ['-o', 'BatchMode=yes', 'etc2nd-shlink', `sudo docker exec omniroute node -e "eval(Buffer.from('${encoded}','base64').toString())"`],
  { encoding: 'utf8', maxBuffer: 60 * 1024 * 1024 },
);

const records = JSON.parse(stdout);
const capturedAt = new Date().toISOString();
for (const record of records) await writeFixture(record, capturedAt);

const manifestPath = path.join(outDir, 'manifest.json');
const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
manifest.captured_at = capturedAt;
manifest.notes = (manifest.notes || []).filter(
  (note) => !note.includes('OmniRoute management fixtures were captured through') &&
    !note.includes('OmniRoute management fixtures were refreshed from'),
);
manifest.notes.push(
  'OmniRoute management fixtures were refreshed from etc2nd-shlink via 127.0.0.1:20129 with a temporary manage-scope key deleted immediately after capture.',
);
manifest.files = (await fs.readdir(outDir)).filter((f) => f.endsWith('.json') && f !== 'manifest.json').sort();
await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n');

console.log(`wrote ${records.length} omniroute fixtures`);
for (const record of records) console.log(`${record.name}:${record.status}`);
NODE
```

If a route returns non-200, do not overwrite a previously meaningful fixture
unless that new status is the intended test fixture. Fix the bridge/source route
or remove that endpoint from the capture list first.

For combo fixtures, capture `GET /api/combos` only after the API bridge forwards
FMO combo management routes. Expected unauthenticated/invalid-auth behavior is
an OmniRoute management auth failure, not the bridge-level message
`API port only serves OpenAI-compatible and approved read-only management
routes.` FMO updates existing combo membership with `PUT /api/combos/{id}`;
it must not call `/api/combos/test`, create, delete, or `/v1/combos` for apply.

## Verify cleanup

The temporary DB row must be gone:

```sh
ssh -o BatchMode=yes etc2nd-shlink \
  "sudo docker exec omniroute node -e 'const Database=require(\"better-sqlite3\"); const db=new Database(\"/app/data/storage.sqlite\", {readonly:true}); console.log((db.prepare(\"select count(*) as n from api_keys where name=?\").get(\"fmo-fixture-temp\")||{}).n); db.close();'"
```

Expected output:

```text
0
```

## Verify redaction

Use PCRE2 because the negative API-key check needs lookahead:

```sh
rg --pcre2 -n \
  'Bearer [A-Za-z0-9]|x-api-key|api[_-]?key"\s*:\s*"(?!\[REDACTED\])|cookie=|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|omr_fixture_|fmo-fixture-temp' \
  reference/fixtures/external-responses -i
```

Expected: no matches.

## Targeted tests

Do not run full pytest for fixture-only refresh. Run only ingestion/spec coverage:

```sh
.venv/bin/python -m pytest \
  tests/test_omniroute_fixture_ingestion.py \
  tests/test_omniroute_account_ingestion.py \
  tests/test_live_quota_ingestion.py \
  tests/test_omniroute_free_registry_ingestion.py \
  tests/test_omniroute_catalog_ingestion.py \
  tests/test_spec_coverage.py
```

If tests fail after a valid capture, inspect whether tests pinned old fixture
ordering or seeded operator state. Example: quota tests must not assume
`providers[0]` is a specific provider after live fixture drift.

## Final checks

```sh
git diff --check
git status --short
```

No push without explicit approval.
