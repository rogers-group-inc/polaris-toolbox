# Maintenance schedules

_Generated from Polaris `public/api.html` (section `maintenance`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

A maintenance schedule pauses either **assets** or **path checks** — never both in one schedule — for a one-time window or on a recurrence. An asset in maintenance stops being polled and alerted on; a path check in maintenance stops running on every agent host and on the server, and its `path*` automations neither fire nor send reminders or escalations. An alert already open stays open and recovers on its own once the window ends. All times are the **Polaris server's wall clock**, written `"YYYY-MM-DDTHH:MM"` with no offset — read `GET /maintenance-schedules/server-time` before building one. Every route gates on `maintenanceManagement`; a write applies at once, so a schedule that is already in its window takes effect before the call returns.

### GET /maintenance-schedules

_Gate: maintenanceManagement:read_

`{ schedules: [...] }`, newest first. `?target=assets` or `?target=pathChecks` lists only that kind (`400` on any other value). A schedule is `{ id, name, enabled, criteria, assetIds, pathCheckIds, schedule, suppressChildren, createdBy, createdAt, updatedAt }`.

### GET /maintenance-schedules/server-time

_Gate: maintenanceManagement:read_

`{ now, timeZone, offsetMinutes }` — the server's wall clock in the form every schedule time uses, its IANA zone, and its UTC offset (east-positive).

### POST /maintenance-schedules

_Gate: maintenanceManagement:write_

Create a schedule; `201` with `{ schedule }`. Body:

- `name` (required, ≤200), `enabled?` (default `true`).
- **Assets:** `criteria?` (an asset filter — hostname, IP / subnet, model, manufacturer, OS, asset type, integration, behind-FortiGate; not status) and / or `assetIds?` (≤500). Only monitored assets enter. `suppressChildren?` (default `true`) marks devices behind an asset in maintenance as down for dependency suppression.
- **Path checks:** `pathCheckIds` (≤500), instead of the two above. `400` on a body carrying both, or naming a check that does not exist.
- `schedule`: a one-time window `{ "version": 1, "kind": "oneshot", "startAt", "endAt" }` — or `"startNow": true` in place of `startAt` to start at the server's own *now* — or a recurrence `{ "version": 1, "kind": "recurring", "freq": "daily" | "weekly" | "monthly" | "yearly", … }` with `daysOfWeek` (weekly, 0 = Sunday), `dayOfMonth` (monthly) or `month` + `day` (yearly), and `hours: [{ startTime, endTime }]` (`"HH:MM"`; an end at or before the start runs past midnight; omitted = all day), plus optional `activeFrom` / `activeUntil` dates.

A one-time schedule naming a single asset or a single path check, with no criteria, removes itself once its window has ended.

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"ERP upgrade","pathCheckIds":["<check id>"],"schedule":{"version":1,"kind":"oneshot","startNow":true,"endAt":"2026-11-01T06:00"}}' \
  "$POLARIS_URL/api/v1/maintenance-schedules"
```

### PUT /maintenance-schedules/:id

_Gate: maintenanceManagement:write_

Replace a schedule — the full body `POST` takes, not a patch: a field you leave out returns to its default (`suppressChildren` to `true`). Disabling one ends its open windows at once.

### DELETE /maintenance-schedules/:id

_Gate: maintenanceManagement:write_

`204`. Its open windows end at once; assets return to the status they had, path checks resume running.

### GET /maintenance-schedules/occurrences?from=YYYY-MM-DD&to=YYYY-MM-DD

_Gate: maintenanceManagement:read_

`{ from, to, truncated, occurrences: [{ scheduleId, name, enabled, kind, adhoc, target, start, end }] }` — every schedule's windows over the day range (at most 400 days), times in the server's wall clock. `target` is `assets` or `pathChecks`.

### GET /maintenance-schedules/path-checks/:checkId

_Gate: maintenanceManagement:read_

`{ inMaintenance, windows: [...], schedules: [{ id, name, enabled, kind, activeNow, nextStart, nextEnd }] }` — whether the check is paused now, by which windows (the `/path-checks` row's shape), and every schedule that names it. `404` for an unknown check.

### POST /maintenance-schedules/path-checks/:checkId/release

_Gate: maintenanceManagement:write_

`{ released }` — ends the check's maintenance now, so it resumes on its agents' next config refresh. A recurring schedule takes it again at its next occurrence, not later in this one; a one-time schedule naming only this check is removed. `released: false` when it was not in maintenance.

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/maintenance-schedules/path-checks/<check id>/release"
```
