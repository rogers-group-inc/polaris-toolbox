# IPAM: Reservations

_Generated from Polaris `public/api.html` (section `ipam-reservations`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

Single-IP (or full-subnet) entries. Reads: `reservations:read`; writes: `reservations:write`, ownership-scoped like networks (tokens need `fullwrite` to edit/delete/retry). Every reservation carries a `sourceType` — `manual` for API/UI-created rows, discovery types (`dhcp_lease`, `dhcp_reservation`, `vip`, `interface_ip`, `dns_resolved`, `observed`, …) for rows Polaris observed. `observed` is an IPv6 address a FortiGate saw a client using without assigning it (SLAAC or static); it carries an `expiresAt` a day past its last sighting. An IPv6 `ipAddress` is stored in its compressed lower-case form, and is never pushed to a FortiGate.

### GET /reservations

_Gate: reservations:read_

`{ reservations, total, limit, offset }` (default limit 50, **max 200**). Filters: `subnetId`, `owner`, `projectRef`, `status` (`active` / `expired` / `released`).

### POST /reservations

_Gate: reservations:write_

Body: `{ subnetId, ipAddress?, hostname, owner?, projectRef?, expiresAt?, notes?, macAddress? }`. Omit `ipAddress` to reserve the whole subnet. `201` with the reservation. An all-zero `macAddress` (`00:00:00:00:00:00`, any separators) is a `400`: it names no device. Omit it instead.

Collision semantics: an existing *active* row at the same address is a `409` — unless it is merely observed presence (`dhcp_lease`, `dns_resolved`, `observed`, or a lease-backed infra row), which the create supersedes in place. Device-owned rows (`vip`, `interface_ip`) and authoritative types always `409`. A deprecated subnet refuses new reservations.

On a network whose integration pushes DHCP reservations, `notes` becomes the FortiGate entry's description, which FortiOS holds 255 characters of — including the `Polaris/: &hellip; []` wrapper Polaris writes around it. An over-length `notes` (or `hostname`) is a `400` naming the budget and the overage; nothing is truncated. The same applies to `PUT /reservations/:id` when it changes either field. Networks Polaris does not push to have no such limit.

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subnetId":"'$SUBNET_ID'","ipAddress":"10.20.30.40","hostname":"printer-3"}' \
  "$POLARIS_URL/api/v1/reservations"
```

### POST /reservations/next-available

_Gate: reservations:write_

Reserve the next free IPv4 address in a subnet: same body minus `ipAddress`. Dry-run: POST `/reservations/next-available/preview` (`reservations:read`) with `{ subnetId, count (≤64), contiguous? }` → `{ ips, count, contiguous }`, creating nothing.

### PUT /reservations/:id

_Gate: reservations:write (own rows) / fullwrite_

Body: `{ hostname?, owner?, projectRef?, expiresAt?, notes?, macAddress? }` (`macAddress: ""` clears it; changing it to the all-zero MAC is a `400`, while sending back a zero the row already holds is accepted). `409` for non-active rows and for device-owned rows: a FortiGate VIP or interface address is configured on the device itself and cannot be edited or released from Polaris.

### DELETE /reservations/:id

_Gate: reservations:write (own rows) / fullwrite_

Release. `204`; `409` when already released/expired or device-owned.

### GET /reservations/push-queue

_Gate: reservations:read_

Reservations awaiting a FortiGate DHCP push (`{ reservations, count }`; `/push-queue/count` returns just `{ count }`). Retry one via POST `/reservations/:id/retry-push` → `{ outcome, reservation }`.
