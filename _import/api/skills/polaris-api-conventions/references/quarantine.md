# Quarantine (SIEM flow)

_Generated from Polaris `public/api.html` (section `quarantine`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

Network quarantine pushes MAC-based address-group entries to every FortiGate that has recently sighted the device. Gates: `assetsQuarantine:read` for reads, `assetsQuarantine:write` for actions — and a token whose role grants quarantine write is additionally **scoped to the integrations picked when the token was minted**; pushes touching any other integration are refused with a `403`.

The recommended flow for a SIEM integration:

### GET /assets/quarantine-availability

_Gate: assetsQuarantine:read_

Preflight — is quarantine push configured anywhere? `{ pushEnabled, integrationCount, pushEnabledCount }`. With `pushEnabled` false a push can only fail ("0/0 FortiGate(s) accepted").

### GET /assets?search=<mac|ip|hostname>

_Gate: assets:read_

Find the asset id. `search` matches MAC, IP, and hostname in one parameter, so pass whatever identifier the SIEM event carries.

### POST /assets/:id/quarantine

_Gate: assetsQuarantine:write_

Body: `{ "reason": "..." }` (optional, ≤500 chars). Response: `{ assetId, status, targets, succeededCount, failedCount, message }` with a per-FortiGate `targets[]` breakdown.

Refusals: `400` for infrastructure types (firewall / switch / access point) and for a device with no known MAC; `409` with no recent sightings (nothing to push to); `502` when zero FortiGates accepted the push (the device's status is *not* flipped in that case).

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"EDR: credential theft detected"}' \
  "$POLARIS_URL/api/v1/assets/$ASSET_ID/quarantine"
```

### POST /assets/:id/quarantine/verify

_Gate: assetsQuarantine:write · rate-limited_

Re-reads each FortiGate to confirm the quarantine entries are still in place. Response: `{ targets, driftDetected }`; drift is persisted and audited. This is the one machine-facing endpoint with its own rate limiter (300 requests / 5 min / source IP — far above a healthy verify cadence).

### GET /assets/:id/quarantine-status

_Gate: assetsQuarantine:read_

`{ id, status, statusBeforeQuarantine, quarantineReason, quarantinedAt, quarantinedBy, quarantineTargets }`.

### DELETE /assets/:id/quarantine

_Gate: assetsQuarantine:write_

Release. Restores the device's prior status and monitoring; device-side unpush failures are reported (`{ assetId, newStatus, unpushedFrom, failedToUnpush, message }`) but never block the release. `409` when the device is not quarantined.

### POST /assets/bulk-quarantine

_Gate: assetsQuarantine:write_

Body: `{ "ids": [...], "reason": "..." }` (≤500 ids). Response `{ results }`, one `{ id, ok, message }` per input in order — one bad asset never fails the batch. Release counterpart: POST `/assets/bulk-quarantine/release` with `{ "ids": [...] }`.

### GET /assets/sighting-settings

_Gate: assetsQuarantine:read · PUT at write_

The sighting max-age window (`{ sightingMaxAgeDays }`, default 180) — how recent a FortiGate sighting must be to count as a push target. PUT accepts `{ "sightingMaxAgeDays": 0–3650 }`.

Related refusals elsewhere: `PUT /assets/:id` refuses setting or clearing `status: "quarantined"` directly (use these endpoints), and `DELETE /assets/:id` answers `409` for a quarantined device — release first.
