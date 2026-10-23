---
name: polaris-api-conventions
description: "Client guide for the Polaris IP-management and monitoring REST API (/api/v1): bearer tokens bound to roles, error envelope and status conventions, filter-don't-403 dashboard/NOC feeds, search scopes, IPAM blocks/networks/reservations, the SIEM quarantine flow, Path Monitor path checks (agent-run HTTP / HTTPS / TCP / ICMP reachability checks, their per-host results, latency history and traceroutes), automations (rule CRUD, the /schema vocabulary, preview / dry run), the MIB Database (upload, structure, walk) and manufacturer profiles (metric rows, overrides, custom widgets and state probes, export / import), and the events audit tail, with curl examples. Load when a project calls a Polaris server, needs a POLARIS_TOKEN, quarantines a device from a SIEM/EDR, builds a NOC wallboard or inventory sync, creates or reads path checks (is a service reachable from each site), creates or edits automations over the API, uploads MIBs or builds a manufacturer profile programmatically, or asks what a Polaris endpoint returns."
---

# Polaris API — client conventions

Polaris is an IP-address-management and device-monitoring application (subnets, reservations,
asset inventory, FortiGate-driven discovery, alerting). It exposes a JSON REST API for
external systems: SIEM-driven quarantine, NOC kiosks and wallboards, inventory consumers and
automation scripts. Everything lives under `<polaris-url>/api/v1`; requests and responses are
JSON. **Build against what the developer page documents** (these references are generated
from it) — Polaris has many more endpoints backing its own UI, and those may change without
notice.

## Getting in

1. An administrator mints a token under **Server Settings → API Tokens**; the raw value
   (`polaris_<32-character tail>`) is shown once. Keep it in a secret store; send it as
   `Authorization: Bearer $POLARIS_TOKEN` on every request.
2. Every token is **bound to a Role** and can do exactly what that role's permission matrix
   allows (`none / read / write / fullwrite` per function key). Ask for a purpose-built,
   least-privilege role (e.g. assets read-only, or quarantine write scoped to named
   integrations) rather than an admin-equivalent one.
3. Smoke-test with a cheap read the role allows (`GET /assets?limit=1` → 200). There is no
   introspection endpoint; `GET /auth/me` answers `{"authenticated": false}` for bearer callers.
4. Writes made with a token appear in the Polaris audit log as `api:<token name>`.

## The six contract rules

1. **401 is undifferentiated.** Missing, revoked, expired and malformed tokens all get the same
   401; do not try to tell them apart.
2. **404, not 403, for anything outside your visibility scope** (an alert, a saved dashboard,
   a network scan you may not see). A 403 means the role lacks the permission outright.
3. **Filter-don't-403 feeds.** `/dashboard/noc-summary`, `/dashboard/summary`,
   `/dashboard/filter-options` and `/search` return the sections the role can read and leave
   the rest empty with the response shape unchanged — a read-only kiosk renders whatever it is
   entitled to. Poll them at wallboard cadence (10–30 s); they are cached server-side ~10 s.
4. **Ownership-scoped keys need `fullwrite` for tokens.** Networks, reservations and contacts
   carry an ownership dimension where `write` edits only rows the *session user* created. A
   token has no username, so a `write`-level token can CREATE those rows but gets 403 on every
   edit/delete. Bind IPAM-managing tokens to a role with `fullwrite` on `subnets` /
   `reservations`.
5. **Page with `total`, not `.length`.** Lists return `{ <items>, total, limit, offset }`
   (`total` is the full filtered count); `limit`/`offset` only — there is no `page` parameter
   except on the per-subnet IP map.
6. **Deprecated aliases carry headers.** `/notifications` → `/alerts`,
   `/notification-rules` → `/automations`, `/notification-channels` → `/delivery-channels`
   still answer, with `Deprecation: true` and a `Link: <successor>; rel="successor-version"`
   header. Use the new paths.

Errors are always `{ "error": "<message>" }` with 400 (validation, names the field), 401,
403, 404, 409 (conflicts with current state: overlapping subnet, duplicate reservation,
block with active reservations), 429 (back off — machine-facing limiters are generous, so a
429 usually means a runaway loop), 5xx.

## Which reference

| You need… | Read |
|---|---|
| the overview and the alias table | [references/overview.md](references/overview.md) |
| tokens, roles, the ownership note | [references/authentication.md](references/authentication.md) |
| the error envelope, status codes, rate limits, cache cadence | [references/errors.md](references/errors.md) |
| device inventory reads (`/assets`, sources, sightings, dependencies) and every list filter | [references/assets.md](references/assets.md) |
| the SIEM quarantine flow (preflight → find → quarantine → verify → release, bulk) | [references/quarantine.md](references/quarantine.md) |
| NOC / wallboard feeds and their `feeds=` / `sections=` selectors | [references/dashboard.md](references/dashboard.md) |
| global typeahead, scope prefixes, caps | [references/search.md](references/search.md) |
| IPAM: blocks | [references/ipam-blocks.md](references/ipam-blocks.md) |
| IPAM: networks (subnets), next-available, bulk allocate, archive, exclusions | [references/ipam-subnets.md](references/ipam-subnets.md) |
| IPAM: reservations, next-available, push queue, collision semantics | [references/ipam-reservations.md](references/ipam-reservations.md) |
| Path Monitor: agent-run path checks, their per-host results, history and traceroutes | [references/path-monitor.md](references/path-monitor.md) |
| automations: rule CRUD, the `/schema` vocabulary, preview / dry run, masked `api_call` headers, removal impact | [references/automations.md](references/automations.md) |
| the MIB Database: upload, structure (symbols, OIDs, enums), MIB-aware walk, the bundled standard MIBs | [references/mib-database.md](references/mib-database.md) |
| manufacturer profiles: metric rows, overrides, custom widgets, state probes, widget switches, export / import, aliases | [references/manufacturer-profiles.md](references/manufacturer-profiles.md) |
| the audit tail and how to poll it incrementally | [references/events.md](references/events.md) |
| a minimal client to start from | [examples/polaris-client.ts](examples/polaris-client.ts), [examples/polaris-client.ps1](examples/polaris-client.ps1) |

## The SIEM quarantine flow (short form)

```
GET  /assets/quarantine-availability          # pushEnabled must be true or every push fails
GET  /assets?search=<mac|ip|hostname>&limit=5 # find the asset id (one param matches all three)
POST /assets/:id/quarantine  {"reason": "..."} # per-FortiGate targets[] in the response
POST /assets/:id/quarantine/verify            # later: { targets, driftDetected } (rate-limited)
DELETE /assets/:id/quarantine                 # release; restores prior status + monitoring
```
Refusals: 400 for infrastructure types or no known MAC, 409 with no recent sightings, 502
when zero gates accepted (status is not flipped). Bulk: `POST /assets/bulk-quarantine`
(`ids[]` ≤500, one result per id, one bad asset never fails the batch).

## Path Monitor (short form)

```
GET  /path-checks                              # checks + fleet summary (pathChecks:read)
POST /path-checks/preview-sources  {scope,assetIds}   # dry-run which agent hosts would run it
POST /path-checks  {name, kind, target, scope|assetIds, ...}   # 201 (pathChecks:write)
GET  /path-checks/:id/results                  # latest result per host
GET  /assets/:id/path-check-history?checkId=&range=24h        # one host's series (assets:read)
GET  /assets/:id/path-check-traceroutes?checkId=&limit=10
```
What trips clients up: **`PUT` replaces the whole check** (send every field, not a patch);
a check has **no threshold** and never changes a host's Up / Down, so alerting is an
automation on the `path*` metrics, not a field here; the service limits are stricter than the
request schema — `intervalSec` whole minutes 60–3600, `timeoutMs` **500–30000** and at most
half the interval — so validate against those; targets are IPv4 only, and loopback,
link-local, cloud-metadata, multicast and the Polaris server itself are refused with 400;
409 means a duplicate name or a 51st enabled check. Only hosts running Polaris Agent
0.21.0+ run checks (`supported: false` in results otherwise).

## Keeping this plugin current

The references are generated from the Polaris checkout's `public/api.html`; when Polaris
changes its API page, re-run `scripts/import-api-html.mjs` (see the repo README) and bump the
plugin version. `.claude-plugin/plugin.json` records the source page's sha256.
