# Automations

_Generated from Polaris `public/api.html` (section `automations`). Do not edit by hand — re-run `scripts/import-api-html.mjs`._

An **automation** is a rule: a *trigger* evaluated over the devices its *scope* selects, a *severity*, and what happens when it fires (*actions*, *escalation*, *repeat*, *reset*). Every endpoint gates on `automationManagement`. Two action types need a second key when a rule carrying them is **saved**: a `script` action needs `automationScripts:write`, a `reboot` action needs `assets:write` (`403` otherwise; removing one never needs it). Saving, editing and deleting each write an Event.

The rule body is large and versioned by its own vocabulary, so build against `GET /automations/schema` rather than a hardcoded list: it returns every metric, state field, comparator, aggregation, change type, action type and severity the server accepts, plus the names behind the ids a condition can carry (state probes, path checks, custom widgets). Draft a rule with `POST /automations/preview` before creating it — it reports which devices the draft would cover and how many readings meet it right now, and writes nothing.

### GET /automations

_Gate: automationManagement:read_

`{ rules: [...] }`. Each rule is the stored, normalized (v2) body below plus its `id`, `createdAt`, `updatedAt`. An `api_call` action's custom header values are secrets and come back **masked** (`"••••••••"`).

```bash
curl -H "Authorization: Bearer $POLARIS_TOKEN" \
  "$POLARIS_URL/api/v1/automations"
```

### GET /automations/schema

_Gate: automationManagement:read_

The builder vocabulary: the enums every field takes, each metric's dimensions and units, and `stateProbes`, `pathChecks`, `customWidgets` (id → name, for conditions that carry an id) and `dimensionPickers`. Read it once per session; it changes only when Polaris is updated or a profile, path check or widget is added.

### POST /automations

_Gate: automationManagement:write_

Create a rule; `201` with `{ rule }`. Body (validated against the same schema the UI uses; `400` names the field):

- `name` (required, ≤200), `description?`, `enabled?` (default `true`), `severity?` — `notice | informational | warning | serious | critical` (default `warning`).
- `trigger` (required), one of: `{ type: "asset_metric", metric, operator, threshold, aggregation?, windowPolls?, forPolls?, dimensionFilter? }` (a reading such as `cpuPct`, `hwSensorValue`, `customStateValue`, `pathOk`); `{ type: "asset_state", field, operator, value, forPolls? }` (a state such as `monitorStatus`); `{ type: "host_metric", … }` (the Polaris server itself); `{ type: "event", actionPattern, resourceType?, minLevel?, detailsMatch? }` (an audit Event, glob on its action); `{ type: "change", changeType, dimensionFilter? }`; or `{ type: "composite", kind: "asset" | "host", op: "and" | "or", children, forPolls? }` (a tree of metric / state conditions). Operators are `> >= < <= == !=`. A hold (`forPolls`) and a window (`windowPolls`) count *readings*, not seconds.
- `scope?` — the device filter: `{ "allAssets": true }`, or `assetTypes`, `tags`, `manufacturers`, …, or a `condition` tree. **`{}` selects no devices** except on an `event` trigger. Only monitored devices alert; `POST /automations/preview` lists what a scope selects.
- `actions?` — up to 20, each one of `notify` (a delivery channel id from `/delivery-channels` plus recipients), `api_call`, `script`, `event`, `reboot`; each may carry its own escalation tiers.
- `reset?` — **absent means `manual`** (never clears by itself); `{ "mode": "auto" }` clears when the condition stops.
- `resetActions?`, `repeat?`, `escalation?`, `severityBands?` (numeric metrics only), `bandNotify?`, `cooldownSec?`, `messageTemplate?`, `emailComposition?`, `groupByAsset?` (one alert per device for per-component triggers), `requireAckNote?`, `quietTime?` (`null` = the global schedules apply, `{ ignoreGlobal: true }` = never held, or a policy of its own).

```bash
curl -X POST -H "Authorization: Bearer $POLARIS_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Firewall CPU high","severity":"serious","enabled":false,
       "trigger":{"type":"asset_metric","metric":"cpuPct","operator":">","threshold":90,"forPolls":3},
       "scope":{"assetTypes":["firewall"]},"reset":{"mode":"auto"}}' \
  "$POLARIS_URL/api/v1/automations"
```

An `asset_state` trigger on `monitorStatus == down` is not only an alert: its `missedPolls` is how down detection is defined for its devices, and a device no such automation covers is never declared down. Check `GET /automations/:id/removal-impact` before deleting or disabling one.

### PUT /automations/:id

_Gate: automationManagement:write_

Replace a rule — a **full body**, not a patch; fields left out take their defaults. Read it, change it, send it back. A masked `api_call` header sent back unchanged keeps its stored value, but only while that action's `url` is unchanged — a masked header on a changed URL is a `400`, so a stored token never follows a new destination. `404` when the rule does not exist.

### DELETE /automations/:id

_Gate: automationManagement:write_

`204`. Its open alerts are cleared.

### GET /automations/:id/removal-impact

_Gate: automationManagement:read_

What removing this rule does to down detection: `{ isDownDetection, governs, wouldFallBackToAnother, wouldBecomePassive, sampleHostnames }` — `wouldBecomePassive` devices are covered by no other down-detection rule and would stop being declared down.

### POST /automations/preview

_Gate: automationManagement:write_

Dry-run a draft. Accepts a partial draft: `{ scope }` alone lists the devices it selects; `{ trigger, scope }` evaluates current readings. Returns `{ supported, totalEvaluated, totalAssets?, unmonitoredCount?, meetsCount, matches, carveOut?, … }` — `meetsCount` is how many readings meet the trigger now, and `carveOut` says which devices a more specific rule already owns. Event and change triggers have no current reading and answer `supported: false`. Writes nothing.

### POST /automations/dimension-values

_Gate: automationManagement:read_

`{ metric, dimension, scope, narrow? }` → the values the draft's devices actually report for one condition dimension (sensor classes, interface names, state probe rows…), so a filter names a value that exists. Companion: POST `/automations/poll-cadence` `{ metric?, scope }` → how often those devices take the reading, to turn a hold in polls into seconds.

### GET /automations/scope-options

_Gate: automationManagement:read_

The values a scope filter can name: manufacturers and models in the inventory, IPAM networks. `GET /automations/recipient-users` lists the users a `notify` action can address.

`POST /automations/test-delivery` (send one action of a draft for real, to the caller only) needs a signed-in user and answers `401` to a bearer token — there is no user to deliver it to.
