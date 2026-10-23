# IPAM: Networks (subnets)

_Generated from Polaris `public/api.html` (section `ipam-subnets`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

CIDRs carved from a block. Reads: `subnets:read`. Writes: `subnets:write` — **ownership-scoped**: plain `write` edits/deletes only rows the caller created, which for a bearer token means creates work but edits/deletes need a role with `fullwrite` (see Authentication (see authentication.md)). Polaris enforces no-overlap within a block and containment in the parent block; violations are `409`/`400` with the conflicting CIDR named.

### GET /subnets

_Gate: subnets:read_

`{ subnets, total, limit, offset }` (default limit 50, max 10000). Filters: `blockId`, `status` (`available` / `reserved` / `deprecated`), `tag`.

Each row carries its address usage: `_count.reservations` — reservations holding an address right now (`active` with an `ipAddress`; released and expired rows and whole-network reservations are not counted); `usableHosts` — addresses the CIDR can hand out, `null` for IPv6 and for any CIDR that cannot be measured; `utilizationPercent` — the first over the second, to one decimal, `null` wherever `usableHosts` is; `totalReservations` — every reservation row on the network whatever its status, which is what a delete removes.

### GET /subnets/:id

_Gate: subnets:read_

One network including its block and full `reservations[]`.

### GET /subnets/:id/ips

_Gate: subnets:read_

The per-address map: `{ subnet, ips, ipv6, totalIps, page, pageSize }`, each `ips[]` entry `{ address, type, reservation, assetId }`. Paged via `page` (default 1) + `pageSize` (default 256, max 65536). IPv6 networks list only reservation-backed addresses.

### POST /subnets

_Gate: subnets:write_

Body: `{ blockId?, cidr, name, purpose?, vlan? (1–4094), tags? }`. Omit `blockId` and the network is placed in the most specific block whose range contains the CIDR; name one and it is used as given. The response carries `block: { id, name, cidr }` — where it landed. `201`; `409` on overlap or duplicate; `400` when the CIDR is invalid, outside the block, the wrong IP version, or (no `blockId`) inside no block at all.

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cidr":"10.20.30.0/24","name":"branch-30","vlan":30}' \
  "$POLARIS_URL/api/v1/subnets"
```

### POST /subnets/next-available

_Gate: subnets:write_

Auto-allocate the next free subnet of a given size: `{ blockId, prefixLength (8–32), name, purpose?, vlan?, tags? }` → `201` with the created network; `409` when no gap of that size remains. IPv4 blocks only.

### POST /subnets/bulk-allocate

_Gate: subnets:write_

Allocate a whole site plan in one transaction: `{ blockId, prefix, entries: [{ name, prefixLength, vlan?, skip? }], tags?, anchorPrefix? }` → `{ created, anchorCidr, effectiveAnchorPrefix }`. All-or-nothing. Dry-run first via POST `/subnets/bulk-allocate/preview`, which answers `{ fits, assignments, error, ... }` with problems reported in `error` (HTTP 200) rather than a 4xx.

### PUT /subnets/:id

_Gate: subnets:write (own rows) / fullwrite_

Body: `{ name?, purpose?, status?, vlan?, tags?, convertToManual? }`.

### DELETE /subnets/:id

_Gate: subnets:write (own rows) / fullwrite_

`204`; `409` while the network holds active reservations (the gate's own `interface_ip` reservation does not count). `?force=true` deletes it anyway, reservations included, and is accepted only from an admin-equivalent role (users + roles fullwrite) — `403` otherwise. A forced delete removes Polaris records only; nothing is unpushed from a FortiGate.

### POST /subnets/:id/refresh

_Gate: subnets:write_

Re-pull one discovered network's addresses from its FortiGate now: `{ lastDiscoveredAt, created, updated, released, skipped }`. `400` for manually-created networks or non-Fortinet integrations.

### GET /subnets/resolve-block?cidr=

_Gate: subnets:read_

The block a new network with this CIDR would be placed in: `{ block: { id, name, cidr } }`, or `{ block: null }` when no block contains it (or the CIDR is invalid).

### GET /subnets/:id/move-targets

_Gate: subnets:read_

Blocks other than the current one whose range contains this network's CIDR: `[{ id, name, cidr, overlaps }]`. `overlaps` is the CIDR of the network in that block that would collide, or `null` when the move is allowed.

### POST /subnets/:id/move

_Gate: subnets:write_

Body `{ blockId }`. Re-parents the network onto another block and returns the updated row; reservations and history stay with it. Ownership-scoped like `PUT`. `400` when the block does not contain the CIDR, the IP version differs, or it is already the network's block; `409` when a network in the destination overlaps.

### POST /subnets/:id/archive

_Gate: subnets:fullwrite_

Retire a network: its definition and every reservation it held are copied into the archive, then the live row is deleted — which frees the CIDR so a replacement FortiGate serving the same address space can be recorded. Returns `{ archivedSubnetId, cidr, reservationCount }`. Unlike `DELETE`, active reservations do not block it: nothing is destroyed, only moved.

### GET /subnets/archived

_Gate: subnets:read_

Retired networks, newest first: `{ archivedSubnets, total, limit, offset }`. Filters `?cidr=` (substring), `?blockId=`, `?fortigateSerial=`. Read `total` for the unpaged match count. Default `limit` 50, max 200.

### GET /subnets/archived/:id

_Gate: subnets:read_

One retirement with every reservation it held, ordered by address. Archived entries are read-only — they exist for review, and no write path can reach them.

### GET /subnets/exclusions

_Gate: subnets:read_

CIDRs declared out of scope for the networks list. An excluded range is never recorded as a network and never raises a conflict — it is how address space several sites serve identically (a management VLAN, an out-of-band range) stops being one row every site fights over. Each row carries `matchCount` plus up to 20 `matches` naming the live networks it covers: adding an exclusion reports those and deliberately leaves them in place.

### POST /subnets/exclusions

_Gate: subnets:fullwrite_

Body `{ cidr, name, notes? }`. IPv4 only; the CIDR is normalized (host bits zeroed) and a duplicate returns `409`. An exclusion covers itself and anything inside it, so a `/16` excludes the `/24`s within it — a WIDER network is deliberately not covered. Returns the created row including `matchCount` / `matches`.

### PUT /subnets/exclusions/:id

_Gate: subnets:fullwrite_

Body `{ name?, notes? }`. There is no `cidr` field: the CIDR is the exclusion’s identity, and re-pointing one in place would silently un-exclude the space it was created for. To change the range, delete the exclusion and add the new one.

### DELETE /subnets/exclusions/:id

_Gate: subnets:fullwrite_

Stop excluding. Discovery may record that address space as a network again on its next run.
