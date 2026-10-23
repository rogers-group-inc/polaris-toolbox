# Path Monitor

_Generated from Polaris `public/api.html` (section `path-monitor`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

A **path check** is an HTTP / HTTPS request, a TCP connect or a ping that the **Polaris Agent** (0.21.0 or later) runs from each host it is pointed at, with an optional traceroute of the path. A check's hosts are its Sources filter plus any pinned assets, *intersected with hosts running an active agent*. A check has no threshold of its own and never changes a host's Up / Down status: alert on it with an automation on the `path*` metrics (`pathOk`, `pathLatencyMs`, `pathFailurePct`, `pathHttpStatus`, `pathHopCount`, `pathTlsDaysLeft`) or on the `path_check.path_changed` event. Check endpoints gate on the `pathChecks` key; the per-host readings under `/assets/:id` gate on `assets:read`, because they describe that asset.

A check can also run from **the Polaris server itself** (`runOnServer: true`), alone or beside agent hosts. The server is not an asset: its results come back as the first `/results` row (`server: true`, `assetId: null`) and through the three `/path-checks/:id/server…` readings. They raise an automation alert only on a `path*` trigger (or the `path_check_path_changed` change trigger) carrying `"includeServer": true` — a single condition, never with a `reset.mode` of `condition` — and that alert has `assetId: null` and `assetHostname: "Polaris server"`. A `path*` automation's devices are always its scope ANDed with *Polaris Agent installed*, and a composite may not mix `path*` conditions with any other. **Pointing the server at a target also needs `networkScan:write`** — creating a server-run check, turning the server on, changing what a server-run check sends, or re-enabling one returns `403` without it. Turning the server off, renaming a check or changing its agent hosts does not need it.

### GET /path-checks

_Gate: pathChecks:read_

`{ checks: [...] }`, by name. Each check carries its definition (below) plus a fleet summary: `sourceCount` (hosts running it), `okCount` / `failCount` (hosts whose latest run passed / failed — a host with no result yet is in neither), `unexpectedCount` (of the failing, those whose run still got an HTTP answer, just not the expected status or body) and `lastRunAt`.

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/path-checks"
```

### GET /path-checks/:id

_Gate: pathChecks:read_

One check, same shape as a list row. `404` when it does not exist.

### GET /path-checks/:id/results

_Gate: pathChecks:read_

`{ results: [...] }` — every host running the check with its latest result, by hostname, after the Polaris server's own row when it runs there (`server: true`, `assetId: null`, `hostname: "Polaris server"`; every host row has `server: false`): `assetId, hostname, ipAddress, os, explicit` (pinned rather than matched), `lastOk, lastSampleAt, lastLatencyMs, lastHttpStatus, lastError, lastResolvedIp, lastFailAt, lastHopCount, lastTracerouteComplete, lastTracerouteAt`, and the agent's `agentVersion, online, supported` (`false` below 0.21.0 — the host is a member but cannot run it).

### POST /path-checks

_Gate: pathChecks:write_

Create a check; `201` with the stored check. Body:

- `name` (required, ≤120, unique — `409` on a duplicate), `description?`, `enabled?` (default `true`).
- `kind`: `http` | `https` | `tcp` | `icmp`. `target`: a full URL for HTTP / HTTPS (no credentials in it), `host:port` for TCP, a bare host for ICMP. IPv4 only. Refused with `400`: loopback, link-local, cloud-metadata and multicast addresses, and this Polaris server itself.
- `intervalSec?` — whole minutes, 60–3600, default 60. `timeoutMs?` — 500–30000, default 5000, and at most half the interval.
- `http?` (HTTP / HTTPS only): `{ expectStatus?` — e.g. `"200,204,300-399"`, empty = any 2xx; `bodyMatch?: { mode: "contains" | "regex" | "exact", pattern (≤1024), caseSensitive? }`; `verifyTls?` (default `true`), `method?` (`"GET"` | `"HEAD"` — nothing that writes is ever sent), `hostHeader?` (sent as Host and used for TLS), `followRedirects?` (≤5 hops, default off) `}`; `bodyMatch.negate?` makes it "must NOT". A regex must be RE2-compatible (no look-around or back-references) — the agent runs it. A check using `method` HEAD, `hostHeader`, `followRedirects` or `negate` needs agent 0.23.0; older agents are listed `supported: false` and run nothing.
- `credentialId?` (HTTP / HTTPS only) — an `http` credential (Bearer, Basic or Digest) to authenticate with. It makes the check **server-only**: it sets `runOnServer`, agent `scope` / `assetIds` are refused with `400`, and the secret is never sent to an agent. Using it — for a check or a test run — needs at least `credentials:read` (`403` otherwise); changing the credential is the `/credentials` routes' business. A credential in use cannot be deleted (`409`).
- `traceroute?: { enabled?` (default `true`), `everyNRuns?` (1–100, default 5), `maxHops?` (1–64, default 30), `probesPerHop?` (1–5, default 3), `probeTimeoutMs?` (100–5000, default 1000) `}`. A trace also runs whenever a passing check starts failing.
- `keepBodyExcerpt?` — keep the first 4 KB of the response on every run, not only on failures.
- `scope?` — the automation device-filter tree (`{ "allAssets": true }` for every agent host), and `assetIds?` (≤2000) to pin hosts regardless of the filter.
- `sourceFilter?` — `{ condition }` or `null`: the filter the UI used to *find* hosts before ticking them into `assetIds`. Stored and returned for display only; it never decides who runs the check. Dropped on a server-run check.
- `runOnServer?` (default `false`) — also run the check from the Polaris server. Needs `networkScan:write`, else `403`. At least one of `scope`, `assetIds` and `runOnServer` must select something.

`409` when the new check would be the 51st enabled one. A host runs at most 20 checks, the oldest first; past that, the newer ones stay listed as members but are not run, and a `path_check.agent_over_cap` event is written.

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"ERP web","kind":"https","target":"https://erp.example.com/health","http":{"expectStatus":"200"},"scope":{"allAssets":true}}' \
  "$POLARIS_URL/api/v1/path-checks"
```

### PUT /path-checks/:id

_Gate: pathChecks:write_

Replace a check — the full body `POST` takes, not a patch. Agents pick the new definition up on their next heartbeat; the server on its next run. `403` without `networkScan:write` when it turns `runOnServer` on, or changes what a server-run check sends (anything but its name, description and hosts), or re-enables one.

### POST /path-checks/:id/enabled

_Gate: pathChecks:write_

`{ enabled: boolean }`. A disabled check keeps its hosts and their last results; agents and the server stop running it. Re-enabling a server-run check needs `networkScan:write`.

### DELETE /path-checks/:id

_Gate: pathChecks:write_

`204`. Removes the check and its host list.

### POST /path-checks/preview-sources

_Gate: pathChecks:write_

Dry-run a Sources selection without saving: body `{ scope?, assetIds? }`. Returns `{ total, ids[], pinned, matchedWithoutAgent, agents[], pinnedWithoutAgent[], minAgentVersion }`; `ids` is every selected host id (up to 2000, so a caller can select all past the row cap); `agents` (first 100) is `{ assetId, hostname, ipAddress, os, agentVersion, online, supported, pinned, pinnedOnly }`.

### POST /path-checks/test

_Gate: pathChecks:write + networkScan:write_

Run a *draft* check once from the Polaris server and return what came back — the body `POST /path-checks` takes, with `name` and the sources optional. Nothing is stored except a `path_check.tested` audit event. Returns `{ source: "server", sample, headers, httpVersion, body }`: `sample` is one run's result fields (the verdict under the draft's expectations, timings, `httpStatus`, TLS facts, `error`); `headers` (≤60, lower-cased, `Set-Cookie` values redacted) and `body` (the first 64 KB it was judged on) are HTTP / HTTPS only, else `null`. The same target refusals as a save (`400`); `429` past 10 test runs a minute per caller.

### GET /path-checks/filter-schema

_Gate: pathChecks:read_

The fields, operators and option lists the `scope` filter accepts — the same vocabulary as an automation's device filter.

### GET /path-checks/:id/server

_Gate: pathChecks:read_

The server source in the `/assets/:id/path-checks` shape: `{ checks: [ check + latest + latestSample ] }`, or `{ checks: [] }` when the check does not run on the server. `404` when the check does not exist.

### GET /path-checks/:id/server/history

_Gate: pathChecks:read_

The server's series for the check — the same `range=` / `from=` + `to=` and the same response as `/assets/:id/path-check-history`.

### GET /path-checks/:id/server/traceroutes

_Gate: pathChecks:read_

The newest traceroutes the server ran for the check, newest first (`limit=` 1–50, default 10) — the same shape as `/assets/:id/path-check-traceroutes`.

### GET /assets/:id/path-checks

_Gate: assets:read_

`{ checks: [...] }` — the checks this host runs, each with its definition, `latest` (the result fields listed under `/results`) and `latestSample` (the newest run in full, including `bodyMatched, bodySha256, bodyBytes, bodyExcerpt, tlsNotAfter, tlsIssuer`). Empty when the host runs none.

### GET /assets/:id/path-check-history?checkId=

_Gate: assets:read_

One check's series from this host. `checkId` is required; `range=` `1h | 12h | 24h | 7d | 30d` (default 24h), or `from=` + `to=` (ISO, ≤1 year). Returns `{ range, checkId, since, until, tier, bucketSeconds, samples }`. On the `detail` tier a sample is one run: `{ timestamp, ok, latencyMs, dnsMs, connectMs, tlsMs, ttfbMs, httpStatus, hopCount, error }`, with a timing field `null` when it was not measured. On `hourly` / `daily` each sample is a bucket carrying averages plus `okCount, failCount, sampleCount, minLatencyMs, maxLatencyMs`.

### GET /assets/:id/path-check-traceroutes?checkId=

_Gate: assets:read_

The newest traceroutes this host ran for one check, newest first: `limit=` 1–50, default 10. Returns `{ checkId, traceroutes }`; each is `{ timestamp, destinationIp, complete, hopCount, pathHash, reason` (`scheduled` or `transition` — taken because the check started failing), `note, hops }`. A hop is `{ ttl, ip, rdns, rttMs[] }` (`ip: null` and `-1` RTTs for probes that got no reply), plus `assetId, hostname, monitorStatus, interfaceName, subnetCidr` when the address belongs to something Polaris knows, as it stood when the trace was stored.
