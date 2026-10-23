# Dashboard & NOC feeds

_Generated from Polaris `public/api.html` (section `dashboard`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

Aggregate wallboard/kiosk feeds. All three endpoints follow the **filter-don't-403 contract**: sections the token's role cannot read come back *empty with the response shape unchanged*, never as an error — so a read-only kiosk token renders whatever it is entitled to. Responses are cached server-side for ~10 s and shared across callers.

### GET /dashboard/noc-summary

_Gate: per-feed: assets/events/alerts/maintenanceManagement read_

The NOC feed bundle. `?feeds=` selects a comma-separated subset of `status, downNodes, downInterfaces, downIpsecTunnels, topCpu, topMemory, slowestResponse, packetLoss, diskUsage, temperature, storageForecast, stalePolls, sitesWithIssues, recentReboots, activeAlerts, maintenanceSchedules`; absent = all. Filters: `hideAssetTypes` (CSV of the asset types to EXCLUDE — built-in or operator-added; `assetTypes` is the legacy inverse and names the ENABLED built-ins, from which the hidden set is derived as the built-ins it omits — sending both unions them), `regionTags`, `fortigates` (all CSV), `limit` (≤1000; each feed has its own default cap), `samples` (top-N averaging depth, ≤100, default 10), `includeDependencyDown=1`.

Response is a flat map of the requested feeds. Three feeds fan out: `status` → `statusCounts` + `uptimePercent` + `activeAlertCount`; `downNodes` → `downNodes` + `downNodesTotal` (true uncapped count); `activeAlerts` → `activeAlerts` + `activeAlertsTotal`. Feed gates: `recentReboots` needs `events:read`, `activeAlerts` needs `alerts:read`, `maintenanceSchedules` needs `maintenanceManagement:read`, everything else `assets:read`.

`maintenanceSchedules` lists the maintenance schedules in effect right now — `{id, name, deviceCount, matchedCount, filtered, assetTypes[{assetType, count}], kind, adhoc, suppressChildren, startedAt, endsAt, endsAtUtc}`, soonest-ending first. `startedAt`/`endsAt` are the Polaris *server's* local wall clock (`YYYY-MM-DDTHH:MM`, no offset — the recurrence engine evaluates against that clock), and `endsAtUtc` is the same window end as a true instant for computing a countdown. Unlike every other feed, an asset filter does not narrow the rows: a schedule is listed when ANY of its devices is in scope and is then reported whole, with `matchedCount` giving the in-scope share.

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/dashboard/noc-summary?feeds=status,downNodes,activeAlerts&limit=50"
```

### GET /dashboard/summary

_Gate: per-section: ipBlocks/reservations/assets read_

`?sections=` subset of `blocks, recent, assetTypes, monitorAlerts` (absent = all). Response keys (only requested sections appear): `blockUtilization`, `recentReservations` (`recentSourceTypes` + `recentLimit` ≤1000 filter it), `assetTypeCounts`, and `monitorAlerts` + `monitorAlertsOverflow` (list capped at 50).

### GET /dashboard/filter-options

_Gate: assets:read_

`{ assetTypes, regions, fortigates, tags }` — the values the dashboard widget filters accept. `assetTypes` is `{ name, label }` entries: every built-in type followed by every operator-added type the asset-type registry carries (plus any custom name still worn by a live asset whose registry row is gone), registry-labelled. `tags` is the distinct asset tags across the live fleet, `region:` tags excluded (they are `regions`). Empty arrays (not 403) without `assets:read`.
