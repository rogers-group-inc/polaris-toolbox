# Assets & inventory

_Generated from Polaris `public/api.html` (section `assets`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

Device inventory reads. Gate: `assets:read` unless noted.

### GET /assets

_Gate: assets:read_

List devices. Response: `{ assets, total, limit, offset }` — `total` is the full filtered count, so page with it rather than `assets.length`.

Query parameters:

- `limit` (default 50, max 10000), `offset` (default 0). There is no `page` parameter.
- `search` — case-insensitive match across hostname, DNS name, IP, MAC, asset tag, and assigned-to.
- `status`, `assetType`, `monitor` — comma-separated multi-value. `monitor` accepts `Unmonitored, Monitored, Dep. Down, Up, Missed, Warning, Down, Recovering, Passive, Pending`.
- Per-column text filters: pass the column name (`hostname`, `ipAddress`, `serialNumber`, `assetTag`, `manufacturer`, `model`, `os`, `macAddress`, `assignedTo`, `purchaseOrder`, `dnsName`, `description`) plus an optional `Op` of `contains` (default), `not_contains`, `empty`, `is_not_empty`.
- `ipAddress` also takes `ipAddressOp=in_networks`: a comma-separated list of IPv4 networks, matched when the primary IP falls in *any* of them. Each entry is a partial address (`10.1` = 10.1.0.0/16), a full address (exact) or a CIDR (`10.1.16.0/20`); at most 50, and an invalid entry is a `400`.
- `department` (contains match), `lastSeenFrom` / `lastSeenTo` (`YYYY-MM-DD`).
- `sortBy` (whitelisted column names; an unknown value is a `400`) + `sortDir` (`asc` default when sorting; default order without `sortBy` is newest first).

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/assets?search=fw-&status=active&limit=25"
```

### GET /assets/:id

_Gate: assets:read_

One device — the full asset record at the top level (not wrapped), including monitoring state, discovered attributes, associated IPs and MAC addresses. `404` when absent.

`addressConfidence` scores every address on the device, keyed by IP: `{ "10.20.30.4": { score, evidenceScore, discoveryScore, band, evidenceBand, parts, penalties, sustained } }`. `score` is 0–100 and includes an operator's pin or typed address; `evidenceScore` is the network evidence alone; `discoveryScore` (0–100) is discovery's evidence alone — no operator, no polling — and is what the automatic pin release compares. `band` is `high` (80 and up), `medium` (50), `low` (20) or `very-low`. Each entry in `parts` is one kind of evidence — `{ kind, label, device, seenAt, hours, value }`: the device's own interface table, a gate seeing it online (kind `detected-ambiguous`, and worth far less, when the gate's ARP table shows that network card with several addresses), a held DHCP reservation or lease, a configured reservation, an ARP entry on a gate, the management IP a FortiGate, FortiSwitch or FortiAP record names, a vCenter guest or host IP, a Proxmox, Unraid or TrueNAS host, VM or container record, an Azure Arc profile, a FortiGate endpoint record, a Generic API feed, or how long Polaris's own polling has answered on it — and each entry in `penalties` is `{ kind, factor, detail }`, a multiplier applied to the score: `alive-elsewhere`, `claimed-elsewhere`, or `arp-elsewhere` — the address rests on what a gate detected, no ARP entry backs it, and a gate's ARP table has that MAC at a different address. `sustained` is true while Polaris's own polling is answering on the address: its evidence is then not aged in `score` and `evidenceScore`, while `discoveryScore` still ages it. Nothing alerts on the score; it only picks the address an unpinned device moves to and when a pin is released. The list (`GET /assets`) carries the compact form, `{ score, band }` per address.

### GET /assets/:id/sources

_Gate: assets:read_

Which discovery sources claim this device (Entra / Intune / AD / FortiGate / vCenter / agent / manual …). Response: a JSON array of `{ id, sourceKind, externalId, integration, observed, firstSeen, lastSeen }`.

### GET /assets/:id/sightings

_Gate: assetsQuarantine:read_

FortiGate DHCP/endpoint sighting history — where the device was last seen on the network. Response: a JSON array, newest first, each row carrying the FortiGate, source, IP, timestamps, plus resolved `subnetName` and `vlan`. Note the gate: this read belongs to the quarantine key, not `assets`.

### GET /assets/:id/dependencies

_Gate: assets:read_

The device's dependency context: `{ asset, effectiveParents, computedParents, overrideParents, hasOverride, children, childrenTruncated, childCount, haPeer }`. `children` lists infrastructure-type children only, capped at 300 (`childrenTruncated` flags overflow). Every node — `asset`, each `effectiveParents[].parent`, `haPeer`, each child and grandchild — carries `activeAlert`: `{ severity, count, unacknowledged }` for its uncleared alerts (worst severity first), or `null` when nothing is firing. Every node also carries `serialNumber` and `ipAddress`: a hostname is not an identity (FortiLink fleets name their switch-ids per site, so two switches in one tree can both read "IDF-1"), and a client telling them apart needs one of those two fields.

Creating a device and putting it under monitoring is **two calls**: `POST /assets` carries inventory fields only, and the monitoring switch plus its credential wiring live on `PUT /assets/:id`. Credentials themselves are *not* created over the API in the normal flow — an operator saves them once under Server Settings → Credentials and the integration references the stored row by id.

### GET /assets/ip-check

_Gate: assets:read_

Ask, before creating or re-addressing a device, whether an address is already in use. Query: `ip` (required), `excludeAssetId` (the asset being edited, so it is not reported as colliding with itself), and optionally `assetType` and `macAddress` for the incoming device. Returns `{ ip, holders[], wouldConflict, qualifiedBy, canMerge }`: every network-present asset already recording the address (each with `claimCurrent` — a stale record is listed but does not collide), whether saving would raise a Duplicate IP conflict, and whether the caller may merge assets (`assets:fullwrite`). The answer is computed with the same rules the save applies, so a `wouldConflict: true` here is a conflict the write will raise. `400` on an invalid address.

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN"   "$POLARIS_URL/api/v1/assets/ip-check?ip=10.20.30.4&assetType=switch"
```

### POST /assets

_Gate: assets:write_

Create a device. Body (all optional, but give it at least an address or a hostname): `{ ipAddress?, macAddress?, hostname?, dnsName?, assetTag?, serialNumber?, manufacturer?, model?, assetType?, status?, location?, latitude?/longitude?, department?, assignedTo?, os?, acquiredAt?, warrantyExpiry?, purchaseOrder?, notes?, description?, tags? }`. `assetType` defaults to `other` and `status` to `active`. An all-zero `macAddress` is stored as no MAC (on `PUT /assets/:id` it clears the field). `azure:` tags in `tags` are dropped: that namespace is mirrored from Azure resource tags by the Azure Arc integration and nothing else may write it. `201` with the created record, plus `ipConflict`: when the new device's address is already recorded by another network-present asset, Polaris raises a Duplicate IP conflict on the spot (rather than on its ten-minute sweep) and returns it as `{ conflictId, ip, qualifiedBy, members[] }`; otherwise `null`. Ask before writing with `GET /assets/ip-check` below.

**Monitoring fields are not accepted here** — `monitored` and every `*CredentialId` belong to the PUT below. A device created by this endpoint is a manual-source asset: only response time gets a source default (ICMP), so every other stream stays dark until a polling method is chosen for it.

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN"   -H "Content-Type: application/json"   -d '{"hostname":"sw-branch-12","ipAddress":"10.20.30.4","assetType":"switch"}'   "$POLARIS_URL/api/v1/assets"
```

### PUT /assets/:id

_Gate: assets:write_

Update any field `POST /assets` accepts, plus the monitoring surface: `{ monitored?, monitorCredentialId?, monitorIntervalSec? (5–86400), probeTimeoutMs? (100–60000) }`, the per-stream polling methods `{ responseTimePolling?, cpuMemoryPolling?, temperaturePolling?, interfacesPolling?, lldpPolling?, storagePolling? }` (one of `rest_api, snmp, winrm, ssh, icmp, agent, vcenter, fortimanager, disabled`), and the per-stream credentials `{ responseTimeCredentialId?, cpuMemoryCredentialId?, temperatureCredentialId?, interfacesCredentialId?, lldpCredentialId? }`. `null` clears a slot and falls back to the next settings tier. When the update *changes* `ipAddress`, the response carries `ipConflict` exactly as `POST /assets` does — the conflict on the new address, or `null` — and a conflict the device just moved off is closed in the same call. `tags` replaces the device's tags, except that its `azure:` tags (Azure Arc's) are always kept and any `azure:` tag in the body is ignored.

Refusals worth coding against:

- `400` — `Credential … not found`, naming the id. It is well-formed but matches no stored credential (commonly one deleted and recreated in the UI, which issues a new id).
- `400` — a credential whose **type** cannot serve the stream's transport, e.g. an `ssh` credential on a stream polling over SNMP. The pairing is `snmp→snmp`, `winrm→winrm`, `ssh→ssh`, `rest_api→restapi`; ICMP, Disabled, Agent, vCenter and FortiManager take no per-asset credential, and a credential left beside one of those is accepted as staged config. `monitorCredentialId` is never type-checked — it is the fallback for every stream at once, and those streams may legitimately poll over different transports.
- `400` — a polling method the asset's discovery source does not support, or ICMP on any stream but response time.
- `409` — `monitored: true` on a status that cannot carry monitoring (decommissioned / disposed / lost / disabled). Change status first.
- `400` — setting or clearing `status: "quarantined"` (use the quarantine endpoints below).

```bash
curl -X PUT -H "Authorization: Bearer $POLARIS_TOKEN"   -H "Content-Type: application/json"   -d '{"monitored":true,"cpuMemoryPolling":"snmp","cpuMemoryCredentialId":"'$CRED_ID'"}'   "$POLARIS_URL/api/v1/assets/$ASSET_ID"
```

### POST /assets/bulk-monitor

_Gate: assets:write_

Flip monitoring on many devices at once: `{ ids: [uuid, …], monitored, monitorCredentialId?, monitorIntervalSec?, probeTimeoutMs? }` → `{ updated, errors: [{ id, error }] }`. A mixed selection is normal, so per-id problems (an unknown id, a status that cannot be monitored) are **reported in `errors` with HTTP 200** while the rest of the batch still applies. An unknown `monitorCredentialId` is the exception and fails the whole call with `400` — it applies to every id in the batch, so nothing would be written correctly.

### POST /assets/bulk-tags

_Gate: assets:write_

Add, remove or replace tags on many devices at once: `{ ids: [uuid, …], mode: "add" | "remove" | "replace", tags: [string, …] }` → `{ updated, unchanged, notFound: [uuid, …], tags }`. `add` keeps each device's own tags and appends the new ones; `remove` strips them from the devices that carry them; `replace` leaves each device with exactly `tags`, except that `region:`, `prev-entra:`, `prev-ad:` and `azure:` tags are kept. An `azure:` tag in `tags` is ignored in every mode — Azure Arc owns that namespace. Unknown ids come back in `notFound` with HTTP 200. An empty `tags` is a `400` for add and remove (replace with none clears), as is adding a `region:` tag that names no map region.

### DELETE /assets/:id

_Gate: assets:write_

`204`. `409` for a quarantined device — release it first.

### PUT /assets/:id/primary-address

_Gate: assets:write_

Pin the address the device is monitored on: `{ mac, ip }` → `{ assetId, mac, ip }`. The pair must be one of the device's own addresses — an entry in `associatedIps` on `GET /assets/:id`, each of which names its `mac`, the gate that reported it (`device`) and `medium`. Reading `GET /assets/:id` first checks the device's DHCP lease and reservation entries against IPAM: one IPAM has released, or holds for a different MAC, is dropped from the list. `ipAddress` becomes the pinned IP and discovery stops changing it; the one exception is a renumber — when the pinned IP has not been seen for 24 hours and the same MAC now has exactly one recently seen address, the pin moves to it. Pinning replaces an IP typed through `PUT /assets/:id`, and typing or clearing the IP there, or `ipRevertToDiscovered`, releases the pin. The device's identity `macAddress` is not changed.

- `409` — the pair is not on the device's address list (type an address that is not there through `PUT /assets/:id` instead).
- `409` — a FortiGate, FortiSwitch or FortiAP managed by a Fortinet integration; it is monitored on its management IP.
- `400` — `mac` is not a MAC address.
- `400` — `ip` is an IPv6 address; use `PUT /assets/:id/primary-ipv6`.

```bash
curl -X PUT -H "Authorization: Bearer $POLARIS_TOKEN"   -H "Content-Type: application/json"   -d '{"mac":"AA:BB:CC:DD:EE:FF","ip":"10.20.30.4"}'   "$POLARIS_URL/api/v1/assets/$ASSET_ID/primary-address"
```

### DELETE /assets/:id/primary-address

_Gate: assets:write_

Release the pin → `{ ipAddress }`. The device moves to the address on its own list (`associatedIps`) with the highest `evidenceScore` — network evidence including polling, no operator weight; a tie keeps the current address. Only when the list is empty does the address go back to what discovery reports (a device no source reports keeps the one it has). A device with no pin is left as it is.

### PUT /assets/:id/primary-ipv6

_Gate: assets:write_

Pin the device's primary IPv6 address: `{ ip }` → `{ assetId, ipv6Address }`. The primary IPv6 is `ipv6Address` on `GET /assets/:id`; it is shown beside `ipAddress` and never replaces it. A device with no `ipAddress` is monitored on it. Without a pin Polaris picks it from the device's IPv6 entries in `associatedIps`; a pinned one is left alone. The address is stored in canonical form.

- `409` — IPv6 is off for this Polaris install.
- `400` — `ip` is not an IPv6 address, or is loopback, link-local or multicast.

```bash
curl -X PUT -H "Authorization: Bearer $POLARIS_TOKEN"   -H "Content-Type: application/json"   -d '{"ip":"2001:db8::4"}'   "$POLARIS_URL/api/v1/assets/$ASSET_ID/primary-ipv6"
```

### DELETE /assets/:id/primary-ipv6

_Gate: assets:write_

Release the pin → `{ ipv6Address }`, the automatic choice made straight away (`null` when the device has no IPv6 address, or IPv6 is off). A device with no pin is left as it is.

### POST /assets/:id/address-check

_Gate: assets:write_

Score an address before pinning it or typing it in: `{ ip, probe? }` → `{ ip, evidenceScore, evidenceBand, score, band, discoveryScore, sustained, parts, penalties, warn, warnBelow, probe }`. The fields are those of `addressConfidence` on `GET /assets/:id`; an address the device has never been seen on scores 0. `warn` is true when `evidenceScore` is below `warnBelow` (50). With `probe: true` the server sends the address one ping (2-second timeout) and `probe` is `{ answered, error }`, otherwise `null` — a reply shows something answers there, not that it is this device, so it is reported beside the score rather than counted in it. Only a check: nothing is written, and `PUT /assets/:id` and `PUT /assets/:id/primary-address` never refuse a low score.

- `400` — `ip` is not an IP address.
- `404` — no such device.

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN"   -H "Content-Type: application/json"   -d '{"ip":"10.20.30.4","probe":true}'   "$POLARIS_URL/api/v1/assets/$ASSET_ID/address-check"
```

### GET /credentials

_Gate: credentials:read_

List stored monitoring credentials so an integration can resolve the id it needs by name: a JSON array of `{ id, name, type, config, createdBy, createdAt }` with **every secret masked** (community strings, passwords, private keys, passphrases and API tokens all read `••••••••`). `type` is one of `snmp, winrm, ssh, restapi, http`.
