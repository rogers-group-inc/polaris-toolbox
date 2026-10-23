# Events (audit tail)

_Generated from Polaris `public/api.html` (section `events`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

The audit log — the natural SIEM *pull* companion to the quarantine push. Retention is 7 days by default (older rows are pruned; syslog/SFTP archival is the long-term store).

### GET /events

_Gate: events:read_

`{ events, total, limit, offset }` (default limit 50, **max 200**).

- `level`, `resourceType` — comma-separated multi-value (levels: `info`, `warning`, `error`; resource types enumerable via `GET /events/resource-types`).
- `action`, `resourceName`, `actor`, `message` text filters, each with an optional `Op` (`contains` default, `not_contains`, `empty`, `is_not_empty`).
- `resourceId` exact match; `since` / `until` timestamps (floored by the retention window).
- `assetId` — every event *about* one asset, whatever it is filed under: the asset's own `resourceType=asset` rows plus its alerts' `notification.*` rows (fired, escalated, cleared). Every returned event carries an `assetId` field (`null` when it is about no single asset).
- `sortBy` ∈ `timestamp, level, action, resourceType, resourceName, actor, message` + `sortDir`; default newest first. Sorting by `level` orders by severity, not alphabetically.

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/events?level=warning,error&since=2026-09-01T00:00:00Z&limit=200"
```

To tail incrementally, page with `offset` inside a `since` window, or track the newest `timestamp` you have seen and pass it as the next poll's `since`.
